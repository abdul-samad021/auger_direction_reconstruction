"""Independent saved-artifact audit; no production predictor/fitter is imported."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "final"
REFERENCE_C = 0.299792458


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    hashes = json.loads((RUN / "artifact_hashes.json").read_text())
    for relative, expected in hashes.items():
        target = (RUN / relative).resolve()
        assert target.is_relative_to(RUN), relative
        assert digest(target) == expected, relative
    config = json.loads((RUN / "configuration.json").read_text())
    assert config["expected_fits"] == 28800
    for relative, expected in config["sources"].items():
        assert digest(RUN / "sources" / relative) == expected
    total = 0
    objective_relative_error = 0.0
    rms_absolute_error = 0.0
    angle_absolute_error = 0.0
    generated_mean_error = 0.0
    quadratic_boundary_count = 0
    repeat_identical = 0
    for path in sorted(RUN.glob("g*.json")):
        payload = json.loads(path.read_text())
        original = json.loads((ROOT / "full" / path.name).read_text())
        assert payload["fits"] == original["fits"], "Reporting fixes changed numerical results"
        repeat_identical += len(payload["fits"])
        spec = payload["scenario"]
        data = np.load(path.with_suffix(".npz"))
        assert digest(path.with_suffix(".npz")) == payload["input_sha256"]
        theta, phi = np.deg2rad([spec["zenith_deg"], spec["azimuth_deg"]])
        truth = np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])
        np.testing.assert_allclose(truth, data["truth_sky"], atol=1e-15, rtol=0)
        positions, core = data["positions_m"], data["core_m"]
        offsets = positions - core
        radius = np.linalg.norm(np.cross(offsets, truth), axis=1)
        expected_mean = 100000 - offsets @ truth / REFERENCE_C + 80 * radius**2 / 1e6
        if spec["regime"] == "asymmetric_mean":
            transverse = np.array(
                [np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)]
            )
            expected_mean += 30 * radius * (offsets @ transverse) / 1e6
        mean_error = np.max(np.abs(expected_mean - data["mean_times_ns"]))
        assert mean_error < 1e-8
        generated_mean_error = max(generated_mean_error, float(mean_error))
        assert np.all(data["actual_sigma_ns"] > 0)
        assert np.all(data["reported_dt_ns"] > 0)
        np.testing.assert_allclose(
            data["observed_times_ns"],
            data["mean_times_ns"] + data["actual_sigma_ns"] * data["standardized_noise"],
            rtol=0,
            atol=0,
        )
        if spec["regime"] == "radial_underreported":
            counterpart = np.load(RUN / f"g{spec['base_index']:02d}_radial_calibrated.npz")
            np.testing.assert_array_equal(
                data["observed_times_ns"], counterpart["observed_times_ns"]
            )
        for row in payload["fits"]:
            assert row["success"]
            parameters = np.array(row["optimizer_parameters"])
            sky = np.r_[parameters[1:3], 1.0]
            sky /= np.linalg.norm(sky)
            np.testing.assert_allclose(sky, row["sky_direction"], rtol=0, atol=1e-14)
            times = data["observed_times_ns"][row["trial"]]
            model, weighting = row["method"].split("_")
            scales = data["reported_dt_ns"] if weighting == "timing" else np.ones(len(times))
            if model == "plane":
                weights = scales**-2
                origin = np.sum(positions * weights[:, None], axis=0) / np.sum(weights)
                epoch = np.sum(times * weights) / np.sum(weights)
                prediction = epoch + parameters[0] - (positions - origin) @ sky / REFERENCE_C
                parameter_count = 3
            else:
                rho = np.linalg.norm(np.cross(offsets, sky), axis=1)
                prediction = times[0] + parameters[0] - offsets @ sky / REFERENCE_C
                prediction += parameters[3] * rho**2 / 1e6
                parameter_count = 4
                quadratic_boundary_count += "curvature_at_lower_bound" in row["quality_flags"]
            residual = times - prediction
            independent_objective = float(np.sum((residual / scales) ** 2))
            relative = abs(independent_objective - row["objective_sum_squares"]) / max(
                1.0, row["objective_sum_squares"]
            )
            assert relative < 1e-7
            objective_relative_error = max(objective_relative_error, relative)
            rms = float(np.sqrt(np.mean(residual**2)))
            rms_difference = abs(rms - row["rms_residual_ns"])
            assert rms_difference < 1e-7
            rms_absolute_error = max(rms_absolute_error, rms_difference)
            nominal = np.sum((residual / data["reported_dt_ns"]) ** 2) / (
                len(times) - parameter_count
            )
            np.testing.assert_allclose(
                nominal, row["nominal_reduced_chi_square"], rtol=1e-7, atol=1e-8
            )
            angle = float(
                np.rad2deg(2 * np.arctan2(np.linalg.norm(sky - truth), np.linalg.norm(sky + truth)))
            )
            angle_difference = abs(angle - row["angular_error_deg"])
            assert angle_difference < 1e-10
            angle_absolute_error = max(angle_absolute_error, angle_difference)
            total += 1
    controls = json.loads((RUN / "exact_controls.json").read_text())
    assert len(controls) == 96
    matched = [item for item in controls if item["matching"]]
    assert len(matched) == 72
    assert all(row["angular_error_deg"] < 1e-5 and row["rms_residual_ns"] < 1e-4 for row in matched)
    assert total == 28800
    result = {
        "audited_fit_count": total,
        "identical_fit_records_to_prior_full_run": repeat_identical,
        "verified_artifacts": len(hashes),
        "maximum_relative_objective_difference": objective_relative_error,
        "maximum_rms_difference_ns": rms_absolute_error,
        "maximum_angle_difference_deg": angle_absolute_error,
        "maximum_independent_mean_generation_difference_ns": generated_mean_error,
        "quadratic_curvature_boundary_fits": quadratic_boundary_count,
        "exact_matching_controls": len(matched),
        "audit_source_sha256": digest(Path(__file__)),
        "status": "passed",
    }
    target = ROOT / "independent_audit.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(target)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
