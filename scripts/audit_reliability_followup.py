"""Independent fixed-core uncertainty replay, separate from the fitted covariance.

This audit uses a nuisance-projected two-dimensional information matrix rather
than the study's full four-parameter covariance calculation. It imports no
production fitter or uncertainty implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


def finite_array(value, shape=None):
    """Reject non-real, nonfinite and incorrectly shaped replay inputs."""
    original = np.asarray(value)
    if original.dtype.kind not in "iuf":
        raise ValueError("Expected finite real numerical input.")
    result = np.asarray(original, dtype=float)
    if not np.isfinite(result).all() or (shape is not None and result.shape != shape):
        raise ValueError("Nonfinite input or invalid shape.")
    return result


def tangent_basis(sky):
    """Construct an orthonormal tangent basis with no azimuth singularity."""
    sky = finite_array(sky, (3,))
    if not np.isclose(np.linalg.norm(sky), 1.0, rtol=0, atol=1e-10):
        raise ValueError("Expected a unit sky direction.")
    axis = np.eye(3)[np.argmin(np.abs(sky))]
    first = np.cross(sky, axis)
    first /= np.linalg.norm(first)
    return np.column_stack((first, np.cross(sky, first)))


def replay_covariance(positions, uncertainties, core, sky, curvature_delay_ns):
    """Marginalize time/curvature by QR projection; return Cartesian sky covariance.

    This is an independent replay of the *same local approximation*, not a
    replacement for empirical coverage or a proof of nonlinear validity.
    """
    positions = finite_array(positions)
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) < 5:
        raise ValueError("Positions need shape (N,3), N >= 5.")
    sigma = finite_array(uncertainties, (len(positions),))
    core = finite_array(core, (3,))
    sky = finite_array(sky, (3,))
    curvature = finite_array(curvature_delay_ns, ())
    if np.any(sigma <= 0) or curvature < 0:
        raise ValueError("Uncertainties must be positive and curvature nonnegative.")
    basis = tangent_basis(sky)
    offsets = positions - core
    projection = offsets @ sky
    perpendicular = np.cross(offsets, sky)
    radius_squared = np.sum(perpendicular**2, axis=1)
    angular = -(offsets @ basis) * (1.0 / 0.299792458 + 2.0 * curvature * projection / 1e6)[:, None]
    nuisance = np.column_stack((np.ones(len(positions)), radius_squared / 1e6))
    nuisance /= sigma[:, None]
    scales = np.linalg.norm(nuisance, axis=0)
    if np.any(scales == 0):
        raise ValueError("Unidentifiable nuisance columns.")
    normalized = nuisance / scales
    if np.linalg.matrix_rank(normalized, tol=1e-10) != 2:
        raise ValueError("Unidentifiable nuisance columns.")
    q, _ = np.linalg.qr(normalized, mode="reduced")
    whitened = angular / sigma[:, None]
    efficient = whitened - q @ (q.T @ whitened)
    _, singular, right = np.linalg.svd(efficient, full_matrices=False)
    if singular[-1] <= 1e-10 * singular[0]:
        raise ValueError("Direction not identifiable after nuisance projection.")
    factor = right.T / singular
    covariance = factor @ factor.T
    return basis @ covariance @ basis.T


def replay_angular_error_deg(first, second):
    """Independent stable half-angle evaluation for close or opposite directions."""
    first = finite_array(first, (3,))
    second = finite_array(second, (3,))
    if np.linalg.norm(first) == 0 or np.linalg.norm(second) == 0:
        raise ValueError("Zero-length direction.")
    a, b = first / np.linalg.norm(first), second / np.linalg.norm(second)
    return float(np.rad2deg(2 * np.arctan2(np.linalg.norm(a - b), np.linalg.norm(a + b))))


def replay_mahalanobis(sky, truth, covariance):
    """Project the sphere logarithm at the fitted sky into a separate tangent basis."""
    sky, truth = finite_array(sky, (3,)), finite_array(truth, (3,))
    covariance = finite_array(covariance, (3, 3))
    basis = tangent_basis(sky)
    if not np.isclose(np.linalg.norm(truth), 1.0, atol=1e-10, rtol=0):
        raise ValueError("Truth must be a unit vector.")
    cosine = float(np.clip(sky @ truth, -1.0, 1.0))
    tangent = truth - cosine * sky
    sine = float(np.linalg.norm(tangent))
    angle = float(np.arctan2(sine, cosine))
    if cosine < 0 and sine < 1e-12:
        raise ValueError("Antipodal logarithm is undefined.")
    displacement = basis.T @ tangent * (angle / sine if sine > 1e-15 else 1.0)
    local_covariance = basis.T @ covariance @ basis
    factor = np.linalg.cholesky(local_covariance)
    whitened = np.linalg.solve(factor, displacement)
    return float(whitened @ whitened)


def wilson_interval(successes, total):
    """Independent two-sided 95% Wilson interval for a binomial count."""
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or int(successes) != successes
        or int(total) != total
        or total <= 0
        or not 0 <= successes <= total
    ):
        raise ValueError("Expected integer counts with 0 <= successes <= total > 0.")
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = (
        z / denominator * np.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total**2))
    )
    return [
        0.0 if successes == 0 else float(max(0, centre - spread)),
        1.0 if successes == total else float(min(1, centre + spread)),
    ]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_manifest(directory, mapping):
    """Verify subordinate bytes before examining numbers; prohibit path escape."""
    directory = Path(directory).resolve()
    if not mapping:
        raise ValueError("Empty artifact manifest.")
    for relative, expected in mapping.items():
        path = directory / relative
        if (
            Path(relative).is_absolute()
            or not path.resolve().is_relative_to(directory)
            or path.is_symlink()
            or not path.is_file()
            or digest(path) != expected
        ):
            raise ValueError(f"Invalid artifact path/hash: {relative}")
    return len(mapping)


def _track(maxima, name, actual, stored, *, relative=False, tolerance=1e-7):
    actual, stored = float(actual), float(stored)
    if not np.isfinite([actual, stored]).all():
        raise AssertionError(f"Nonfinite audit metric {name}.")
    difference = abs(actual - stored)
    if relative:
        difference /= max(1.0, abs(actual), abs(stored))
    maxima[name] = max(maxima.get(name, 0.0), difference)
    if difference > tolerance:
        raise AssertionError(f"{name} disagreement: {actual} vs {stored}.")


def _replay_fit(data, row, *, stage_a):
    sky = (
        np.array([row[f"fitted_sky_{axis}"] for axis in "xyz"])
        if stage_a
        else np.asarray(row["sky_direction"])
    )
    sigma = data["reported_sigma_ns" if stage_a else "reported_dt_ns"]
    truth = data["true_sky" if stage_a else "truth_sky"]
    offsets = data["positions_m"] - data["core_m"]
    delay = row["delay_at_1km_ns"]
    core_time = row["fitted_core_time_ns" if stage_a else "core_time_ns"]
    predicted = (
        core_time
        - offsets @ sky / 0.299792458
        + delay * np.sum(np.cross(offsets, sky) ** 2, axis=1) / 1e6
    )
    residuals = (data["observed_times_ns"][int(row["trial"])] - predicted) / sigma
    chi = float(residuals @ residuals)
    covariance = replay_covariance(data["positions_m"], sigma, data["core_m"], sky, delay)
    radius = float(np.rad2deg(np.sqrt(-2 * np.log(0.05) * np.linalg.eigvalsh(covariance)[-1])))
    return {
        "sky": sky,
        "covariance": covariance,
        "major_radius_95_deg": radius,
        "mahalanobis_squared": replay_mahalanobis(sky, truth, covariance),
        "angular_error_deg": replay_angular_error_deg(sky, truth),
        "chi_square": chi,
        "reduced_chi_square": chi / (len(sigma) - 4),
    }


def audit_stage_a(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    artifacts = check_manifest(directory, manifest["files"])
    config = json.loads((directory / "protocol_lock.json").read_text())
    frame = pd.read_csv(directory / "trials.csv")
    expected = len(config["layouts"]) * len(config["directions_deg"]) * len(config["regimes"])
    if len(frame) != expected * config["trials_per_scenario"]:
        raise AssertionError("Stage A attempt count mismatch.")
    if frame.duplicated(["scenario", "trial"]).any():
        raise AssertionError("Duplicate Stage A trial.")
    maxima = {}
    summary = pd.read_csv(directory / "coverage_summary.csv").set_index("scenario")
    replayed = 0
    for scenario, rows in frame.groupby("scenario", sort=True):
        with np.load(directory / f"inputs_{scenario}.npz", allow_pickle=False) as archive:
            data = dict(archive)
        for row in rows.to_dict("records"):
            if not row["fit_success"] or not row["covariance_available"]:
                continue
            result = _replay_fit(data, row, stage_a=True)
            for name in ("angular_error_deg", "major_radius_95_deg", "mahalanobis_squared"):
                _track(maxima, name, result[name], row[name], relative=name != "angular_error_deg")
            _track(
                maxima,
                "relative_chi",
                result["reduced_chi_square"],
                row["reduced_chi_square"],
                relative=True,
            )
            local = np.array(
                [
                    [row["covariance_00_rad2"], row["covariance_01_rad2"]],
                    [row["covariance_01_rad2"], row["covariance_11_rad2"]],
                ]
            )
            basis = tangent_basis(result["sky"])
            stored_cartesian = basis @ local @ basis.T
            error = np.linalg.norm(result["covariance"] - stored_cartesian) / np.linalg.norm(
                result["covariance"]
            )
            _track(maxima, "relative_covariance", error, 0, tolerance=1e-7)
            for probability in (0.68, 0.95):
                level = int(probability * 100)
                covered = result["mahalanobis_squared"] <= -2 * np.log(1 - probability)
                if covered != row[f"covered_{level}"]:
                    raise AssertionError("Replayed coverage decision disagrees.")
            replayed += 1
        available = rows.covariance_available
        for level in (68, 95):
            for label, mask in (
                ("all", np.ones(len(rows), dtype=bool)),
                ("available", available),
                ("interior", available & ~rows.curvature_boundary),
            ):
                total = int(np.sum(mask))
                if total == 0:
                    continue
                count = int(rows.loc[mask, f"covered_{level}"].sum())
                base = f"coverage_{level}_{label}"
                _track(
                    maxima,
                    "summary_proportion",
                    count / total,
                    summary.loc[scenario, base],
                    tolerance=1e-12,
                )
                low, high = wilson_interval(count, total)
                _track(
                    maxima,
                    "summary_interval",
                    low,
                    summary.loc[scenario, base + "_low"],
                    tolerance=1e-12,
                )
                _track(
                    maxima,
                    "summary_interval",
                    high,
                    summary.loc[scenario, base + "_high"],
                    tolerance=1e-12,
                )
    return {
        "passed": True,
        "checked_artifacts": artifacts,
        "attempted_fits": len(frame),
        "replayed_available_fits": replayed,
        "max_discrepancies": maxima,
        "manifest_sha256": digest(directory / "manifest.json"),
    }


def _warning(row, threshold):
    radius = row.get("major_radius_95_deg")
    return bool(
        not row["fit_success"]
        or not row["uncertainty_available"]
        or radius is None
        or not np.isfinite(radius)
        or radius < 0
        or row["curvature_boundary"]
        or radius > threshold
    )


def _counts(rows, threshold, error_limit):
    good = [row for row in rows if row["fit_success"]]
    bad = np.array([row["angular_error_deg"] > error_limit for row in good], dtype=bool)
    flag = np.array([_warning(row, threshold) for row in good], dtype=bool)
    tp, fp = int(np.sum(bad & flag)), int(np.sum(~bad & flag))
    fn, tn = int(np.sum(bad & ~flag)), int(np.sum(~bad & ~flag))
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "retained": fn + tn,
        "fit_failures": len(rows) - len(good),
    }


def audit_stage_b(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    mapping = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
    artifacts = check_manifest(directory, mapping)
    policy = json.loads((directory / "locked_policy.json").read_text())
    lock = json.loads((directory / "policy_lock_receipt.json").read_text())
    generated = json.loads((directory / "validation/generation_started.json").read_text())
    if lock["sha256"] != digest(directory / "locked_policy.json"):
        raise AssertionError("Policy lock hash mismatch.")
    if datetime.fromisoformat(lock["sealed_at_utc"]) >= datetime.fromisoformat(
        generated["started_at_utc"]
    ):
        raise AssertionError("Evaluation generation did not follow policy lock.")
    if policy["development_records_sha256"] != digest(directory / "development/records.json"):
        raise AssertionError("Policy development-data mismatch.")
    results = json.loads((directory / "results.json").read_text())
    phases = {}
    maxima = {}
    development_records = []
    for split in ("development", "validation"):
        records = json.loads((directory / split / "records.json").read_text())
        frame = pd.DataFrame(records)
        if frame.duplicated(["scenario", "trial"]).any() or not (frame.split == split).all():
            raise AssertionError("Duplicated or cross-split records.")
        replayed = 0
        for scenario, rows in frame.groupby("scenario", sort=True):
            with np.load(directory / split / f"{scenario}.npz", allow_pickle=False) as archive:
                data = dict(archive)
            for row in rows.to_dict("records"):
                if row["fit_success"] and row["uncertainty_available"]:
                    result = _replay_fit(data, row, stage_a=False)
                    for name in ("angular_error_deg", "major_radius_95_deg", "chi_square"):
                        _track(
                            maxima,
                            name,
                            result[name],
                            row[name],
                            relative=name != "angular_error_deg",
                        )
                    replayed += 1
                if (
                    split == "validation"
                    and _warning(row, policy["threshold_deg"]) != row["warning"]
                ):
                    raise AssertionError(
                        "Frozen warning decisions disagree with independent replay."
                    )
        counts = _counts(records, policy["threshold_deg"], policy["error_limit_deg"])
        for name, value in counts.items():
            if results[split][name] != value:
                raise AssertionError(f"Stage B aggregate mismatch: {split}/{name}.")
        phases[split] = {"records": len(records), "replayed_available_fits": replayed, **counts}
        if split == "development":
            development_records = records
    config = json.loads((directory / "configuration.json").read_text())
    candidates = []
    for threshold in config["candidate_thresholds_deg"]:
        count = _counts(development_records, threshold, policy["error_limit_deg"])
        positive = count["true_positive"] + count["false_negative"]
        negative = count["false_positive"] + count["true_negative"]
        sensitivity = count["true_positive"] / positive if positive else 0
        false_warning = count["false_positive"] / negative if negative else 1
        candidates.append(
            {
                "threshold": threshold,
                "viable": bool(
                    positive and negative and sensitivity >= 0.9 and false_warning <= 0.3
                ),
                "retained": count["retained"],
                "balanced_accuracy": (sensitivity + 1 - false_warning) / 2,
            }
        )
    viable = [candidate for candidate in candidates if candidate["viable"]]
    selected = max(
        viable or candidates,
        key=lambda x: (x["retained"] if viable else x["balanced_accuracy"], x["threshold"]),
    )
    if (
        selected["threshold"] != policy["threshold_deg"]
        or bool(viable) != policy["development_viable"]
    ):
        raise AssertionError("Frozen policy does not match development-only selection rule.")
    return {
        "passed": True,
        "checked_artifacts": artifacts,
        "policy_locked_before_validation": True,
        "policy_development_selection_replayed": True,
        "phases": phases,
        "max_discrepancies": maxima,
        "manifest_sha256": digest(directory / "manifest.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-a", type=Path, required=True)
    parser.add_argument("--stage-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new audit output path.")
    result = {
        "passed": True,
        "stage_a": audit_stage_a(args.stage_a),
        "stage_b": audit_stage_b(args.stage_b),
        "audit_source_sha256": digest(__file__),
        "completed_utc": datetime.now(UTC).isoformat(),
        "scope": (
            "Independent numerical replay of conditional local approximation, "
            "not detector calibration."
        ),
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
