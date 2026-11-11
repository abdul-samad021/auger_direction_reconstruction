"""Bounded redundant-field audit; never fit or modify historical results.

Run with pyproj 3.7.2 available in an isolated audit environment. Only the
completed training manifest and the previously inspected focus event are read.
The two hypotheses are evaluated against released spDistance/declination,
not chosen by agreement between our fits and Auger's reconstructed direction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pyproj
from pyproj import Transformer

FOCUS = "081847956000"
ORIGIN_E, ORIGIN_N = 477256.66, 6099203.68
UTM = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True)
ECEF = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)
BASELINE = Path("reports/results/training_pilot_20261011_v1")
FOCUS_RUN = Path("reports/results/real_front_comparison_20261010T204030_242582Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def envelope(path: Path) -> dict:
    data = json.loads(path.read_bytes())
    encoded = json.dumps(data["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(encoded.encode()).hexdigest() != data["sha256"]:
        raise ValueError(f"Changed envelope: {path}")
    return data["payload"]


def basis(longitude_deg: float, latitude_deg: float) -> np.ndarray:
    """Right-handed local ENU unit vectors as ECEF columns, geodetic latitude."""
    if not np.isfinite([longitude_deg, latitude_deg]).all() or abs(latitude_deg) > 90:
        raise ValueError("Finite geodetic longitude/latitude required.")
    lon, lat = np.deg2rad([longitude_deg, latitude_deg])
    return np.column_stack(
        (
            [-np.sin(lon), np.cos(lon), 0.0],
            [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)],
            [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)],
        )
    )


def sky(theta_deg: float, phi_deg: float) -> np.ndarray:
    theta, phi = np.deg2rad([theta_deg, phi_deg])
    return np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])


def angle(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(a, b)), a @ b)))


def summary(values: list[float] | np.ndarray) -> dict:
    a = np.asarray(values, dtype=float)
    if not a.size or not np.isfinite(a).all():
        raise ValueError("Nonempty finite sample required.")
    return {
        "count": int(a.size),
        "median": float(np.median(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(np.max(a)),
    }


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def mathematical_checks() -> dict:
    """Round trips and 3D frame covariance of both timing models, independent of fits."""
    lon0, lat0 = UTM.transform(ORIGIN_E, ORIGIN_N)
    np.testing.assert_allclose([lon0, lat0], [-69.25, -35.25], atol=1e-6, rtol=0)
    b0 = basis(lon0, lat0)
    bc = basis(-69.5, -35.1)
    rotation = b0.T @ bc
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-15, rtol=0)
    np.testing.assert_allclose(np.linalg.det(rotation), 1, atol=1e-15, rtol=0)
    rng = np.random.default_rng(20261014)
    offsets = rng.uniform(-5000, 5000, (30, 3))
    direction = sky(43, 237)
    rotated = rotation @ direction
    changed_positions = offsets @ rotation.T
    np.testing.assert_allclose(rotation.T @ rotated, direction, atol=1e-15, rtol=0)
    maximum = 0.0
    for curvature in [0.0, 100.0]:
        t = -offsets @ direction / 0.299792458
        t += curvature * np.sum(np.cross(offsets, direction) ** 2, axis=1) / 1e6
        tr = -changed_positions @ rotated / 0.299792458
        tr += curvature * np.sum(np.cross(changed_positions, rotated) ** 2, axis=1) / 1e6
        np.testing.assert_allclose(t, tr, atol=5e-11, rtol=0)
        maximum = max(maximum, float(np.max(np.abs(t - tr))))
    return {
        "origin_longitude_deg": lon0,
        "origin_latitude_deg": lat0,
        "maximum_timing_change_ns": maximum,
        "status": "passed",
    }


def run(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "scope": "711 previously observed training events plus old focus; no protected files",
        "hypotheses": ["native_site_angles", "core_local_angles_rotated_to_site"],
        "basis": "WGS84 geodetic ENU; UTM19 south; exact supplied UTM origin",
        "selection": "No direction-frame choice based on agreement with our fitted directions",
        "status": "post-email follow-up; focus exploratory check preceded full-sample execution",
        "rounding_check": "conditional conservative bounds, NOT statistical confidence intervals",
        "rounding_assumptions": "theta/phi/dec 0.01deg; positions/spDistance 0.01m",
        "historical_policy": "no refitting, no overwrites, both comparison scenarios saved",
        "limitation": "Site ENU tested empirically; not exporter source proof",
    }
    write_json(output / "audit_protocol.json", protocol)
    checks = mathematical_checks()
    lon0, lat0 = checks["origin_longitude_deg"], checks["origin_latitude_deg"]
    origin_basis = basis(lon0, lat0)
    origin_ecef = np.array(ECEF.transform(lon0, lat0, 1400.0))
    config_path = root / BASELINE / "configuration.json"
    configuration = envelope(config_path)
    identities = configuration["training_ids"]
    if len(identities) != 711 or len(set(identities)) != 711 or FOCUS in identities:
        raise ValueError("Authorized population changed.")
    hashes = {str(config_path.relative_to(root)): digest(config_path)}
    script = Path(__file__).resolve()
    (output / "audit_source.py").write_bytes(script.read_bytes())
    if script.is_relative_to(root):
        hashes[str(script.relative_to(root))] = digest(script)
    focus_path = root / FOCUS_RUN / "all_fit_records_before_reference.csv"
    hashes[str(focus_path.relative_to(root))] = digest(focus_path)
    focus_hashes_path = root / FOCUS_RUN / "input_file_sha256.json"
    hashes[str(focus_hashes_path.relative_to(root))] = digest(focus_hashes_path)
    expected_focus_hash = json.loads(focus_hashes_path.read_bytes())[FOCUS]
    with focus_path.open(newline="") as stream:
        focus_records = [
            r
            for r in csv.DictReader(stream)
            if r["event_id"] == FOCUS and r["stage"] == "full" and r["scenario"] == "baseline"
        ]
    events, stations, comparisons = [], [], []
    for identity in [*identities, FOCUS]:
        if len(identity) != 12 or not identity.isdigit():
            raise ValueError("Invalid authorized event ID.")
        path = root / "data/raw/events" / f"Auger_{identity}.json"
        hashes[str(path.relative_to(root))] = digest(path)
        if identity == FOCUS and digest(path) != expected_focus_hash:
            raise ValueError("Focus input differs from saved predictions.")
        data = json.loads(path.read_bytes())
        if data["info"]["id"] != int(identity):
            raise ValueError("Event identity mismatch.")
        sd = data["sdrec"]
        longitude, latitude = UTM.transform(sd["easting"], sd["northing"])
        rotation = origin_basis.T @ basis(longitude, latitude)
        native = sky(sd["theta"], sd["phi"])
        transformed = rotation @ native
        core = np.array([sd[k] for k in ("x", "y", "z")])
        reconstructed_core = origin_basis.T @ (
            np.array(ECEF.transform(longitude, latitude, sd["altitude"])) - origin_ecef
        )
        angular_rounding = np.deg2rad(0.005) * (
            1 + np.sin(np.deg2rad(min(90, sd["theta"] + 0.005)))
        )
        angular_change = angle(native, transformed)
        event = {
            "event_id": identity,
            "population": "focus" if identity == FOCUS else "train",
            "core_latitude_deg": latitude,
            "core_longitude_deg": longitude,
            "reference_vector_rotation_deg": angular_change,
            "local_vertical_tilt_deg": angle(origin_basis[:, 2], basis(longitude, latitude)[:, 2]),
        }
        for component, residual in zip("xyz", reconstructed_core - core, strict=True):
            event[f"exported_core_{component}_residual_m"] = float(residual)
        for tag, lat in [("site", lat0), ("core", latitude)]:
            pole_projection = native[1] * np.cos(np.deg2rad(lat))
            pole_projection += native[2] * np.sin(np.deg2rad(lat))
            declination = np.rad2deg(np.arcsin(np.clip(pole_projection, -1, 1)))
            event[f"{tag}_declination_residual_deg"] = float(declination - sd["dec"])
        event["declination_rounding_bound_deg"] = float(np.rad2deg(angular_rounding) + 0.005)
        distances = {"site": [], "core": []}
        passing = {"site": 0, "core": 0}
        for station in data["stations"]:
            if station["isSelected"] != 1:
                continue
            delta = np.array([station[k] for k in ("x", "y", "z")]) - core
            # Triangle inequality: <= 0.005m for distance plus two rounded XYZ vectors.
            bound = 0.005 + 2 * np.sqrt(3) * 0.005 + np.linalg.norm(delta) * angular_rounding
            row = {
                "event_id": identity,
                "station_id": station["id"],
                "rounding_bound_m": float(bound),
                "published_axis_distance_m": station["spDistance"],
            }
            for tag, direction in [("site", native), ("core", transformed)]:
                residual = float(np.linalg.norm(np.cross(delta, direction)) - station["spDistance"])
                row[f"{tag}_distance_residual_m"] = residual
                distances[tag].append(abs(residual))
                passing[tag] += abs(residual) <= bound
            stations.append(row)
        event["selected_stations"] = len(distances["site"])
        for tag in ["site", "core"]:
            event[f"{tag}_median_absolute_distance_residual_m"] = summary(distances[tag])["median"]
            event[f"{tag}_max_absolute_distance_residual_m"] = summary(distances[tag])["max"]
            event[f"{tag}_rounding_consistent_stations"] = int(passing[tag])
        events.append(event)
        if identity == FOCUS:
            records = focus_records
        else:
            prediction_path = root / BASELINE / "events" / identity / "predictions.json"
            hashes[str(prediction_path.relative_to(root))] = digest(prediction_path)
            prediction = envelope(prediction_path)
            if prediction["raw_sha256"] != digest(path):
                raise ValueError("Raw event differs from saved fit input.")
            records = [
                r
                for r in prediction["records"]
                if r["stage"] == "full" and r["scenario"] == "baseline" and r["success"]
            ]
        if len(records) != 4 or any(str(r["success"]).lower() != "true" for r in records):
            raise ValueError("Expected four saved successful baseline fits per event.")
        for record in records:
            direction = np.array([record[k] for k in ("sky_x", "sky_y", "sky_z")], dtype=float)
            np.testing.assert_allclose(np.linalg.norm(direction), 1, atol=1e-12, rtol=0)
            old, revised = angle(direction, native), angle(direction, transformed)
            fitted_core = rotation.T @ direction
            np.testing.assert_allclose(revised, angle(fitted_core, native), rtol=0, atol=1e-11)
            if abs(old - revised) > angular_change + 1e-10:
                raise AssertionError("Angular-distance triangle inequality violated.")
            comparisons.append(
                {
                    "event_id": identity,
                    "population": event["population"],
                    "model": record["model"],
                    "weighting": record["weighting"],
                    "site_interpretation_separation_deg": old,
                    "core_local_interpretation_separation_deg": revised,
                    "comparison_change_deg": revised - old,
                    "reference_vector_rotation_deg": angular_change,
                    "fitted_sky_site_x": float(direction[0]),
                    "fitted_sky_site_y": float(direction[1]),
                    "fitted_sky_site_z": float(direction[2]),
                    "fitted_sky_core_x": float(fitted_core[0]),
                    "fitted_sky_core_y": float(fitted_core[1]),
                    "fitted_sky_core_z": float(fitted_core[2]),
                    "fitted_zenith_core_deg": float(
                        np.rad2deg(np.arctan2(np.linalg.norm(fitted_core[:2]), fitted_core[2]))
                    ),
                    "fitted_azimuth_core_deg": float(
                        np.rad2deg(np.arctan2(fitted_core[1], fitted_core[0])) % 360
                    ),
                }
            )
    for name, expected in hashes.items():
        if digest(root / name) != expected:
            raise RuntimeError("Historical input changed during audit.")
    report = {
        "protocol": protocol,
        "mathematical_checks": checks,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyproj": pyproj.__version__,
            "proj": pyproj.proj_version_str,
        },
        "event_count": len(events),
        "selected_station_count": len(stations),
        "focus": next(e for e in events if e["event_id"] == FOCUS),
        "all_events": {},
        "training_comparisons": {},
    }
    for tag in ["site", "core"]:
        report["all_events"][tag] = {
            "event_median_absolute_spDistance_residual_m": summary(
                [e[f"{tag}_median_absolute_distance_residual_m"] for e in events]
            ),
            "station_absolute_spDistance_residual_m": summary(
                [abs(s[f"{tag}_distance_residual_m"]) for s in stations]
            ),
            "stations_within_rounding_bound": sum(
                abs(s[f"{tag}_distance_residual_m"]) <= s["rounding_bound_m"] for s in stations
            ),
            "events_all_selected_stations_within_rounding_bound": sum(
                e[f"{tag}_rounding_consistent_stations"] == e["selected_stations"] for e in events
            ),
            "absolute_declination_residual_deg": summary(
                [abs(e[f"{tag}_declination_residual_deg"]) for e in events]
            ),
            "declinations_within_rounding_bound": sum(
                abs(e[f"{tag}_declination_residual_deg"]) <= e["declination_rounding_bound_deg"]
                for e in events
            ),
        }
    report["core_hypothesis_smaller_distance_error_events"] = sum(
        e["core_median_absolute_distance_residual_m"]
        < e["site_median_absolute_distance_residual_m"]
        for e in events
    )
    report["reference_vector_rotation_deg"] = summary(
        [e["reference_vector_rotation_deg"] for e in events]
    )
    report["local_vertical_tilt_deg"] = summary([e["local_vertical_tilt_deg"] for e in events])
    report["core_export_consistency_m"] = {
        component: summary([abs(e[f"exported_core_{component}_residual_m"]) for e in events])
        for component in "xyz"
    }
    for weighting in ["timing", "uniform"]:
        group = [
            r for r in comparisons if r["population"] == "train" and r["weighting"] == weighting
        ]
        item = {}
        for model in ["plane", "quadratic"]:
            rows = [r for r in group if r["model"] == model]
            item[model] = {
                key: summary([r[key] for r in rows])
                for key in [
                    "site_interpretation_separation_deg",
                    "core_local_interpretation_separation_deg",
                ]
            }
        for scenario in ["site_interpretation", "core_local_interpretation"]:
            key = f"{scenario}_separation_deg"
            pairs = {}
            for row in group:
                pairs.setdefault(row["event_id"], {})[row["model"]] = row[key]
            complete = [v for v in pairs.values() if set(v) == {"plane", "quadratic"}]
            item[scenario] = {
                "paired_events": len(complete),
                "quadratic_farther_events": sum(p["quadratic"] > p["plane"] for p in complete),
            }
        report["training_comparisons"][weighting] = item
    write_csv(output / "event_redundancy_checks.csv", events)
    write_csv(output / "selected_station_redundancy_checks.csv", stations)
    write_csv(output / "saved_fit_reference_comparisons.csv", comparisons)
    # An explicit, auditable evidence gate; not a statistical hypothesis test.
    verified = (
        report["core_hypothesis_smaller_distance_error_events"] == len(events)
        and report["all_events"]["core"]["stations_within_rounding_bound"] == len(stations)
        and report["all_events"]["core"]["declinations_within_rounding_bound"] == len(events)
        and max(v["max"] for v in report["core_export_consistency_m"].values()) < 0.03
    )
    report["operational_frame_verified_by_redundant_fields"] = verified
    report["verification_qualification"] = (
        "Empirical export consistency; not exporter-source proof or absolute pointing calibration. "
        "Evidence gate documented after initial exploration; not a preregistered statistical test."
    )
    if not verified:
        raise ValueError("Frame evidence does not justify a corrected comparison table.")
    corrected = [
        {
            "event_id": r["event_id"],
            "population": r["population"],
            "model": r["model"],
            "weighting": r["weighting"],
            "separation_from_auger_deg": r["core_local_interpretation_separation_deg"],
            "comparison_frame": "core_local_ENU",
            "input_prediction_frame": "central_site_ENU",
            "fitted_zenith_core_deg": r["fitted_zenith_core_deg"],
            "fitted_azimuth_core_deg": r["fitted_azimuth_core_deg"],
            "legacy_mixed_frame_separation_deg": r["site_interpretation_separation_deg"],
        }
        for r in comparisons
    ]
    write_csv(output / "corrected_reference_comparisons.csv", corrected)
    write_json(output / "input_sha256.json", hashes)
    write_json(output / "summary.json", report)
    write_json(
        output / "artifact_sha256.json", {p.name: digest(p) for p in sorted(output.iterdir())}
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.root.resolve(), arguments.output.resolve()), indent=2))
