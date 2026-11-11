"""Read-only coordinate consistency audit; write a new, non-overwriting receipt.

Only completed training-event predictions and the already-observed focus event
are eligible. Auxiliary station coordinates contain no protected event targets.
The official tutorial is parsed as data; none of its cells are executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from auger_reco.data.event_json import load_auger_plane_front_input
from auger_reco.physics import curved_front, plane_front

ORIGIN = np.array([477256.66, 6099203.68, 1400.0])
ALPHA, BETA, EARTH_RADIUS_M = 2.52e-3, 6.03e-4, 6_368_000.0
NOTEBOOK_URL = "https://zenodo.org/records/10488964/files/notebook.zip?download=1"
NOTEBOOK_SHA256 = "3568191c87dacd42ce26b747c2f1ad31a084cd1d87d3f7f7e841dbcf4e6e6138"
FOCUS_ID = "081847956000"
EXTREME_ID = "081881294400"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_envelope(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    encoded = json.dumps(value["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(encoded.encode()).hexdigest() != value["sha256"]:
        raise ValueError(f"Invalid checkpoint envelope: {path}")
    return value["payload"]


def _positions(values: object) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim < 1 or array.shape[-1] != 3 or not np.isfinite(array).all():
        raise ValueError("Positions must be finite with final dimension three.")
    return array


def site_to_tutorial_utm(values: object) -> np.ndarray:
    """Apply the tutorial's first-order horizontal and quadratic altitude map."""
    points = _positions(values)
    result = np.empty_like(points)
    x, y, z = np.moveaxis(points, -1, 0)
    result[..., 0] = ORIGIN[0] + (1 - BETA) * x - ALPHA * y
    result[..., 1] = ORIGIN[1] + (1 - BETA) * y + ALPHA * x
    result[..., 2] = ORIGIN[2] + z + (x * x + y * y) / (2 * EARTH_RADIUS_M)
    return result


def tutorial_utm_to_site(values: object) -> np.ndarray:
    """Invert this approximation algebraically, not the full geodetic export."""
    offsets = _positions(values) - ORIGIN
    result = np.empty_like(offsets)
    e, n, a = np.moveaxis(offsets, -1, 0)
    denominator = (1 - BETA) ** 2 + ALPHA**2
    x = ((1 - BETA) * e + ALPHA * n) / denominator
    y = ((1 - BETA) * n - ALPHA * e) / denominator
    result[..., 0], result[..., 1] = x, y
    result[..., 2] = a - (x * x + y * y) / (2 * EARTH_RADIUS_M)
    return result


def rotation_z(angle_deg: float) -> np.ndarray:
    angle = np.deg2rad(angle_deg)
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    """Independent atan2/cross-product comparison; no fitted angle conversion."""
    return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(a, b)), a @ b)))


def independent_times(positions: np.ndarray, core: np.ndarray, sky: np.ndarray, a: float):
    offsets = positions - core
    longitudinal = offsets @ (-sky)
    transverse_squared = np.sum(np.cross(offsets, sky) ** 2, axis=1)
    return 100_000.0 + longitudinal / 0.299792458 + a * transverse_squared / 1e6


def invariance_checks() -> dict:
    """Check independent forward equations and actual fitter frame covariance."""
    rng = np.random.default_rng(20261013)
    positions = rng.uniform(-1600, 1600, (18, 3))
    positions[:, 2] *= 0.02
    core = np.array([137.0, -219.0, 11.0])
    sigma = np.linspace(7, 22, len(positions))
    translation = np.array([510_000.0, 6_100_000.0, 1400.0])
    records = []
    for phi in (0.0, 90.0, 180.0, 270.0):
        sky = plane_front.sky_direction_from_angles(np.deg2rad(42), np.deg2rad(phi))
        for model, curvature in (("plane", 0.0), ("quadratic", 75.0)):
            times = independent_times(positions, core, sky, curvature)
            for scenario, rotate, shift in (
                ("base", np.eye(3), np.zeros(3)),
                ("translate", np.eye(3), translation),
                ("rotate_z", rotation_z(137), np.zeros(3)),
                ("rotate_and_translate", rotation_z(-83), translation),
            ):
                p, c, direction = (
                    positions @ rotate.T + shift,
                    core @ rotate.T + shift,
                    rotate @ sky,
                )
                forward = independent_times(p, c, direction, curvature)
                np.testing.assert_allclose(forward, times, atol=1e-7, rtol=0)
                if model == "plane":
                    fit = plane_front.fit_plane_front(p, times, sigma)
                    public = plane_front.predict_station_times_ns(100_000, -direction, p, c)
                    np.testing.assert_allclose(public, forward, atol=1e-9, rtol=0)
                else:
                    fit = curved_front.fit_quadratic_front(p, times, sigma, core_position_m=c)
                    np.testing.assert_allclose(fit.delay_at_1km_ns, curvature, atol=1e-4, rtol=0)
                error = angle_deg(fit.sky_direction, direction)
                if error > 1e-5 or np.max(np.abs(fit.residuals_ns)) > 1e-4:
                    raise AssertionError(f"Frame recovery failed: {model}/{phi}/{scenario}")
                records.append(
                    {
                        "model": model,
                        "azimuth_deg": phi,
                        "scenario": scenario,
                        "angular_error_deg": error,
                        "maximum_forward_difference_ns": float(np.max(abs(forward - times))),
                        "maximum_fit_residual_ns": float(np.max(abs(fit.residuals_ns))),
                    }
                )
    # A positive propagation x means a positive-x displacement arrives later.
    expected = np.array([0.0, 100.0 / 0.299792458])
    observed = plane_front.predict_station_times_ns(
        0, [1, 0, 0], [[0, 0, 0], [100, 0, 0]], [0, 0, 0]
    )
    np.testing.assert_allclose(observed, expected, atol=1e-12, rtol=0)
    u = np.array([0.3, 0.4, -np.sqrt(0.75)])
    first = plane_front.predict_station_times_ns(10, u, positions, [0, 0, 0])
    second = plane_front.predict_station_times_ns(10 + core @ u / 0.299792458, u, positions, core)
    np.testing.assert_allclose(first, second, atol=1e-10, rtol=0)
    return {"fit_checks": records, "sign_and_reference_time_checks": "passed"}


def counterfactual_shift(positions: np.ndarray) -> np.ndarray:
    """Deliberately add the altitude term to site z; NOT a physical correction."""
    result = np.array(_positions(positions), copy=True)
    result[..., 2] += np.sum(result[..., :2] ** 2, axis=-1) / (2 * EARTH_RADIUS_M)
    return result


def distribution(values: list[float]) -> dict:
    data = np.asarray(values, dtype=float)
    if data.size == 0 or not np.isfinite(data).all():
        raise ValueError("A summary requires finite, nonempty data.")
    return {
        "count": data.size,
        "median": float(np.median(data)),
        "p95": float(np.percentile(data, 95)),
        "maximum": float(np.max(data)),
    }


def write_json(path: Path, item: dict | list) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(item, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No rows for CSV.")
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(root: Path, output: Path, notebook_archive: Path | None = None) -> dict:
    """Audit existing authorized data; refuse any existing output directory."""
    output.mkdir(parents=True, exist_ok=False)
    protocol = root / "docs/conference_coordinate_audit.md"
    (output / "prespecified_protocol.md").write_bytes(protocol.read_bytes())
    baseline = root / "reports/results/training_pilot_20261011_v1"
    configuration = read_envelope(baseline / "configuration.json")
    training = configuration["training_ids"]
    if len(training) != 711 or len(set(training)) != 711 or FOCUS_ID in training:
        raise ValueError("Unexpected authorized population.")
    identities = [*training, FOCUS_ID]
    if EXTREME_ID not in training:
        raise ValueError("Extreme event is not authorized training data.")
    sources = {
        str(protocol.relative_to(root)): digest(protocol),
        "training_configuration": digest(baseline / "configuration.json"),
    }
    auxiliary = root / "data/raw/archives/auxiliary.zip"
    sources["data/raw/archives/auxiliary.zip"] = digest(auxiliary)
    with zipfile.ZipFile(auxiliary) as archive:
        member = next(p for p in archive.namelist() if p.endswith("sdMap.csv"))
        mapping = {
            int(r["id"]): r for r in csv.DictReader(io.StringIO(archive.read(member).decode()))
        }
    if notebook_archive is None:
        with urllib.request.urlopen(NOTEBOOK_URL, timeout=60) as response:
            tutorial = response.read(10_000_000)
    else:
        tutorial = notebook_archive.read_bytes()
    tutorial_hash = hashlib.sha256(tutorial).hexdigest()
    if tutorial_hash != NOTEBOOK_SHA256:
        raise ValueError("Tutorial archive changed; review its source before using constants.")
    (output / "official_notebook.zip").write_bytes(tutorial)
    with zipfile.ZipFile(io.BytesIO(tutorial)) as archive:
        notebook = json.loads(archive.read("notebook/plot_json.ipynb"))
    cell = "".join(notebook["cells"][32]["source"])
    if not all(token in cell for token in ("2.52e-3", "6.03e-4", "6368000", "stations['Delta A']")):
        raise ValueError("Tutorial coordinate cell no longer matches reviewed source.")
    write_json(
        output / "tutorial_source_receipt.json",
        {
            "url": NOTEBOOK_URL,
            "archive_sha256": tutorial_hash,
            "member": "notebook/plot_json.ipynb",
            "zero_based_cell": 32,
            "source": cell,
            "note": (
                "Tutorial comment says latitude 35.35 S; team email says 35.25 S. "
                "Not resolved here."
            ),
        },
    )
    conversions, shifts, refits, missing, input_hashes = [], [], [], [], {}
    seen = set()
    for identity in identities:
        path = root / f"data/raw/events/Auger_{identity}.json"
        input_hashes[identity] = digest(path)
        event = json.loads(path.read_bytes())
        if int(identity) != event["info"]["id"]:
            raise ValueError("Event identity mismatch.")
        core = event["sdrec"]
        points = [("sd_core", "core", core, core)]
        for station in event["stations"]:
            key = (station["id"], station["x"], station["y"], station["z"])
            if key in seen:
                continue
            seen.add(key)
            if station["id"] not in mapping:
                missing.append({"event_id": identity, "station_id": station["id"]})
                continue
            points.append(
                ("unique_station_position", str(station["id"]), station, mapping[station["id"]])
            )
        for kind, name, site, projected in points:
            position = np.array([site[k] for k in ("x", "y", "z")], dtype=float)
            reference = np.array(
                [projected[k] for k in ("easting", "northing", "altitude")], dtype=float
            )
            calculated = site_to_tutorial_utm(position)
            inverse = tutorial_utm_to_site(calculated)
            np.testing.assert_allclose(inverse, position, rtol=0, atol=1e-8)
            difference = calculated - reference
            conversions.append(
                {
                    "event_id": identity,
                    "kind": kind,
                    "object_id": name,
                    "easting_error_m": difference[0],
                    "northing_error_m": difference[1],
                    "altitude_error_m": difference[2],
                    "earth_altitude_term_m": float(
                        np.sum(position[:2] ** 2) / (2 * EARTH_RADIUS_M)
                    ),
                    "horizontal_radius_m": float(np.linalg.norm(position[:2])),
                }
            )
        measurements = load_auger_plane_front_input(path)
        positions = measurements.station_positions_m
        sigma = measurements.timing_uncertainties_ns
        if identity != FOCUS_ID:
            prediction_path = baseline / "events" / identity / "predictions.json"
            predicted = read_envelope(prediction_path)
            if predicted["raw_sha256"] != input_hashes[identity]:
                raise ValueError("Baseline raw hash changed.")
            input_hashes[f"{identity}/prediction"] = digest(prediction_path)
            record = next(
                r
                for r in predicted["records"]
                if r["stage"] == "full" and r["model"] == "plane" and r["weighting"] == "timing"
            )
            sky = np.array([record[k] for k in ("sky_x", "sky_y", "sky_z")])
        else:
            sky = plane_front.fit_plane_front(
                positions, measurements.observed_times_ns, sigma
            ).sky_direction
        delta = (counterfactual_shift(positions) - positions) @ (-sky) / 0.299792458
        centered = delta - np.average(delta, weights=sigma**-2)
        shifts.append(
            {
                "event_id": identity,
                "stations": len(positions),
                "absolute_maximum_delay_ns": float(np.max(abs(delta))),
                "delay_peak_to_peak_ns": float(np.ptp(delta)),
                "weighted_centered_rms_delay_ns": float(
                    np.sqrt(np.average(centered**2, weights=sigma**-2))
                ),
                "unweighted_centered_rms_delay_ns": float(np.sqrt(np.mean(centered**2))),
            }
        )
        if identity in (FOCUS_ID, EXTREME_ID):
            core_position = np.array([core[k] for k in ("x", "y", "z")])
            for model in ("plane", "quadratic"):
                pair = []
                for changed in (False, True):
                    p = counterfactual_shift(positions) if changed else positions
                    c = counterfactual_shift(core_position) if changed else core_position
                    if model == "plane":
                        fit = plane_front.fit_plane_front(p, measurements.observed_times_ns, sigma)
                    else:
                        fit = curved_front.fit_quadratic_front(
                            p, measurements.observed_times_ns, sigma, core_position_m=c
                        )
                    pair.append(fit)
                base, altered = pair
                refits.append(
                    {
                        "event_id": identity,
                        "model": model,
                        "direction_shift_deg": angle_deg(base.sky_direction, altered.sky_direction),
                        "baseline_reduced_chi_square": base.reduced_chi_square,
                        "counterfactual_reduced_chi_square": altered.reduced_chi_square,
                        "baseline_rms_ns": base.rms_residual_ns,
                        "counterfactual_rms_ns": altered.rms_residual_ns,
                    }
                )
    write_csv(output / "coordinate_crosschecks.csv", conversions)
    write_csv(output / "counterfactual_delays.csv", shifts)
    write_csv(output / "counterfactual_refits.csv", refits)
    write_json(output / "input_hashes.json", input_hashes)
    checks = invariance_checks()
    write_json(output / "invariance_checks.json", checks)
    summaries = {}
    for kind in ("sd_core", "unique_station_position"):
        rows = [r for r in conversions if r["kind"] == kind]
        summaries[kind] = {
            key: distribution([abs(r[key]) for r in rows])
            for key in (
                "easting_error_m",
                "northing_error_m",
                "altitude_error_m",
                "earth_altitude_term_m",
            )
        }
    result = {
        "training_events": len(training),
        "focus_events": 1,
        "protected_event_files_opened": 0,
        "transformation_residuals_absolute_m": summaries,
        "unmatched_station_positions": missing,
        "synthetic_fit_invariance_checks": len(checks["fit_checks"]),
        "counterfactual_only_not_correction": {
            key: distribution([r[key] for r in shifts])
            for key in ("delay_peak_to_peak_ns", "weighted_centered_rms_delay_ns")
        },
        "counterfactual_refits": refits,
        "horizontal_map_rotation_deg": float(np.rad2deg(np.arctan2(ALPHA, 1 - BETA))),
        "horizontal_map_scale": float(np.hypot(1 - BETA, ALPHA)),
        "sources": sources,
    }
    for relative in (
        "scripts/audit_conference_coordinates.py",
        "tests/test_conference_coordinates.py",
        "src/auger_reco/physics/plane_front.py",
        "src/auger_reco/physics/curved_front.py",
        "src/auger_reco/data/event_json.py",
    ):
        result["sources"][relative] = digest(root / relative)
    write_json(output / "summary.json", result)
    write_json(
        output / "artifact_sha256.json",
        {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--notebook-archive", type=Path)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run(arguments.root.resolve(), arguments.output.resolve(), arguments.notebook_archive),
            indent=2,
        )
    )
