"""Independent numerical/provenance audit of complete training checkpoints.

No production timing, angle, fitting, or reporting helpers are used. Protected
event contents are never opened. An audit receipt is new, never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def envelope(path: Path) -> tuple[dict, str]:
    item = json.loads(path.read_bytes())
    text = json.dumps(item["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    expected = hashlib.sha256(text.encode()).hexdigest()
    if item["sha256"] != expected:
        raise ValueError(f"Envelope mismatch: {path}")
    return item["payload"], expected


def separation(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(a, b)), a @ b)))


def audit(run_dir: Path) -> dict:
    config, config_hash = envelope(run_dir / "configuration.json")
    root = Path(config["repository"])
    handoff = root / "reports/results/prepilot_diagnostics_20261010T234353_804166Z"
    manifest = handoff / "pilot_execution_target_free.csv"
    if digest(manifest) != config["execution_manifest_sha256"]:
        raise ValueError("Manifest mismatch")
    with manifest.open(newline="") as stream:
        train = [r["event_id"] for r in csv.DictReader(stream) if r["split"] == "train"]
    if train != config["training_ids"]:
        raise ValueError("Run IDs differ from authorized training population")
    if {p.name for p in (run_dir / "events").iterdir() if p.is_dir()} != set(train):
        raise ValueError("Missing training or unexpected/protected event directory")
    for relative, expected in config["source_hashes"].items():
        if any(digest(p / relative) != expected for p in (root, run_dir / "source_snapshot")):
            raise ValueError(f"Source mismatch: {relative}")
    counts, failures, flags = Counter(), Counter(), Counter()
    max_prediction_difference = max_objective_difference = max_angle_difference = 0.0
    for identity in train:
        directory = run_dir / "events" / identity
        outcome, _ = envelope(directory / "outcome.json")
        receipt, receipt_hash = envelope(directory / "download.json")
        if outcome["configuration_sha256"] != config_hash or (
            outcome["download_sha256"] != receipt_hash
        ):
            raise ValueError(f"Checkpoint chain mismatch: {identity}")
        counts[outcome["status"]] += 1
        raw_hash = receipt["receipt"].get("sha256")
        if (
            raw_hash is not None
            and digest(root / f"data/raw/events/Auger_{identity}.json") != raw_hash
        ):
            raise ValueError(f"Raw mismatch: {identity}")
        if not (directory / "predictions.json").exists():
            continue
        prediction, pred_hash = envelope(directory / "predictions.json")
        if pred_hash != outcome["prediction_sha256"] or (
            prediction["raw_sha256"] != raw_hash or prediction["download_sha256"] != receipt_hash
        ):
            raise ValueError(f"Prediction chain mismatch: {identity}")
        inputs = prediction["inputs"]
        offsets = np.asarray(inputs["positions_m"]) - inputs["published_core_position_m"]
        times, sigmas = (
            np.asarray(inputs["observed_times_ns"]),
            np.asarray(inputs["uncertainties_ns"]),
        )
        n = len(times)
        expected = {
            (stage, index, model, weighting)
            for stage, indices in (("full", [None]), ("leave_one_out", range(n)))
            for index in indices
            for model in ("plane", "quadratic")
            for weighting in ("timing", "uniform")
        }
        records = prediction["records"]
        actual = {
            (r["stage"], r["held_out_station_index"], r["model"], r["weighting"]) for r in records
        }
        if actual != expected or len(records) != 4 + 4 * n:
            raise ValueError(f"Missing, duplicate or unplanned fits: {identity}")
        groups = defaultdict(list)
        for row in prediction["station_residuals"]:
            groups[row["fit_id"]].append(row)
        full_directions = {}
        for row in records:
            counts["fit_attempts"] += 1
            if not row["success"]:
                failures[row["failure_type"]] += 1
                if groups[row["fit_id"]]:
                    raise ValueError("Failed fit has predictions")
                continue
            counts["successful_fits"] += 1
            flags.update(row["quality_flags"])
            sky = np.array([row["sky_x"], row["sky_y"], row["sky_z"]])
            np.testing.assert_allclose(np.linalg.norm(sky), 1.0, atol=1e-12, rtol=0)
            # Cross product independently constructs distance perpendicular to the axis.
            radial_squared = np.sum(np.cross(offsets, -sky) ** 2, axis=1)
            delay = offsets @ (-sky) / 0.299792458
            delay += row["delay_at_1km_ns"] * radial_squared / 1e6
            saved = groups[row["fit_id"]]
            if len(saved) != (n if row["stage"] == "full" else 1):
                raise ValueError("Missing successful-fit predictions")
            first = saved[0]
            intercept = first["predicted_time_ns"] - delay[first["station_index"]]
            predicted = intercept + delay
            retained = np.ones(n, dtype=bool)
            if row["stage"] == "leave_one_out":
                retained[row["held_out_station_index"]] = False
            residual = times - predicted
            chi = float(np.sum((residual[retained] / sigmas[retained]) ** 2))
            objective = (
                chi if row["weighting"] == "timing" else float(np.sum(residual[retained] ** 2))
            )
            dof = int(retained.sum()) - (3 if row["model"] == "plane" else 4)
            for key, value in (
                ("chi_square", chi),
                ("objective_sum_squares", objective),
                ("reduced_chi_square", chi / dof),
                ("rms_residual_ns", float(np.sqrt(np.mean(residual[retained] ** 2)))),
                ("maximum_absolute_residual_ns", float(np.max(np.abs(residual[retained])))),
            ):
                np.testing.assert_allclose(
                    value,
                    row[key],
                    rtol=1e-7,
                    atol=1e-5,
                    err_msg=f"{identity}/{row['fit_id']}/{key}",
                )
            max_objective_difference = max(
                max_objective_difference,
                abs(objective - row["objective_sum_squares"])
                / max(1.0, abs(row["objective_sum_squares"])),
            )
            for station in saved:
                i = station["station_index"]
                max_prediction_difference = max(
                    max_prediction_difference, abs(predicted[i] - station["predicted_time_ns"])
                )
                np.testing.assert_allclose(
                    predicted[i], station["predicted_time_ns"], rtol=0, atol=1e-5
                )
                np.testing.assert_allclose(residual[i], station["residual_ns"], rtol=0, atol=1e-5)
                np.testing.assert_allclose(
                    residual[i] / sigmas[i],
                    station["residual_over_observed_sigma"],
                    rtol=1e-7,
                    atol=1e-6,
                )
            key = (row["model"], row["weighting"])
            if row["stage"] == "full":
                full_directions[key] = sky
            elif key in full_directions:
                np.testing.assert_allclose(
                    separation(sky, full_directions[key]),
                    row["direction_shift_from_full_deg"],
                    atol=1e-9,
                )
        if (directory / "reference_evaluation.json").exists():
            reference, ref_hash = envelope(directory / "reference_evaluation.json")
            if ref_hash != outcome["reference_evaluation_sha256"] or (
                reference["prediction_sha256"] != pred_hash
            ):
                raise ValueError("Reference checkpoint chain mismatch")
            theta = np.deg2rad(reference["reference"]["zenith_deg"])
            phi = np.deg2rad(reference["reference"]["azimuth_deg"])
            sky = np.array(
                [np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)]
            )
            for item in reference["reference_comparisons"]:
                angle = separation(full_directions[item["model"], item["weighting"]], sky)
                max_angle_difference = max(
                    max_angle_difference, abs(angle - item["separation_from_auger_deg"])
                )
                np.testing.assert_allclose(
                    angle, item["separation_from_auger_deg"], rtol=0, atol=1e-9
                )
                counts["reference_comparisons"] += 1
    return {
        "configuration_sha256": config_hash,
        "training_events": len(train),
        "counts": dict(counts),
        "fit_failure_types": dict(failures),
        "quality_flags_by_fit": dict(flags),
        "largest_prediction_recomputation_difference_ns": max_prediction_difference,
        "largest_objective_relative_difference": max_objective_difference,
        "largest_reference_angle_difference_deg": max_angle_difference,
        "metric_rtol": 1e-7,
        "metric_atol": 1e-5,
        "prediction_atol_ns": 1e-5,
        "reference_angle_atol_deg": 1e-9,
        "protected_event_contents_read": 0,
        "audit_script_sha256": digest(Path(__file__)),
        "interpretation": (
            "Internal numerical/provenance consistency, not physical truth validation"
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run_dir.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2))
