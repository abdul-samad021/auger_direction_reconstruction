"""Contracts for the controlled conference stress design, not detector realism."""

from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from auger_reco.evaluation import conference_stress as study
from auger_reco.physics import plane_front


def test_prespecified_grid_and_counts() -> None:
    cases = study.scenarios()
    assert len(cases) == 72
    assert len({case.identifier for case in cases}) == 72
    assert len({case.base_index for case in cases}) == 12
    assert len(cases) * study.TRIALS * len(study.METHODS) == 28800


@pytest.mark.parametrize("layout", study.LAYOUTS)
@pytest.mark.parametrize("count", study.COUNTS)
def test_geometry_is_finite_noncollinear_and_repeatable(layout: str, count: int) -> None:
    positions = study.station_positions(layout, count)
    assert positions.shape == (count, 3)
    assert np.isfinite(positions).all()
    assert np.linalg.matrix_rank(positions[:, :2] - positions[:, :2].mean(axis=0)) == 2
    assert_array_equal(positions, study.station_positions(layout, count))
    if layout == "one_sided":
        assert np.all(positions[:, 0] > study.CORE_M[0])


def test_independent_generator_zero_curvature_and_translation() -> None:
    positions = study.station_positions("well_spread", 13)
    sky, times, radii = study.independent_mean(positions, 25.0, 20.0, curvature_delay_ns=0.0)
    expected = 100000.0 + (positions - study.CORE_M) @ (-sky) / 0.299792458
    assert_allclose(times, expected, rtol=0.0, atol=3e-11)
    shift = np.array([4e5, -2e5, 1400.0])
    _, shifted, shifted_radii = study.independent_mean(
        positions + shift,
        25.0,
        20.0,
        core=study.CORE_M + shift,
        curvature_delay_ns=0.0,
        origin_time_ns=100040.0,
    )
    assert_allclose(shifted, times + 40.0, rtol=0.0, atol=1e-8)
    assert_allclose(shifted_radii, radii, rtol=0.0, atol=1e-8)
    assert np.linalg.norm(sky) == pytest.approx(1.0)
    assert sky[2] > 0.0


def test_asymmetric_mean_is_separate_from_noise() -> None:
    base = study.scenarios()[0]
    gaussian = study.generated_case(base, 8)
    asymmetric = study.generated_case(replace(base, regime="asymmetric_mean"), 8)
    assert_array_equal(gaussian["standardized_noise"], asymmetric["standardized_noise"])
    assert_array_equal(gaussian["actual_sigma_ns"], asymmetric["actual_sigma_ns"])
    assert not np.allclose(gaussian["mean_times_ns"], asymmetric["mean_times_ns"])
    assert_allclose(
        asymmetric["observed_times_ns"] - gaussian["observed_times_ns"],
        np.broadcast_to(
            asymmetric["mean_times_ns"] - gaussian["mean_times_ns"],
            asymmetric["observed_times_ns"].shape,
        ),
        rtol=0.0,
        atol=3e-11,
    )


def test_radial_miscalibration_changes_reported_dt_not_observations() -> None:
    base = study.scenarios()[0]
    calibrated = study.generated_case(replace(base, regime="radial_calibrated"), 20)
    miscalibrated = study.generated_case(replace(base, regime="radial_underreported"), 20)
    for name in ("observed_times_ns", "mean_times_ns", "actual_sigma_ns", "standardized_noise"):
        assert_array_equal(calibrated[name], miscalibrated[name])
    assert np.all(miscalibrated["reported_dt_ns"] < miscalibrated["actual_sigma_ns"])
    assert np.all(miscalibrated["reported_dt_ns"] > 0)
    assert_array_equal(calibrated["actual_sigma_ns"], calibrated["reported_dt_ns"])


@pytest.mark.parametrize("regime", study.REGIMES)
def test_noise_is_centered_unit_variance_without_sample_recentering(regime: str) -> None:
    # Large diagnostic sample verifies the implementation, not a proof from data.
    noise = study.standardized_noise(regime, np.random.default_rng(68314), (200000,))
    assert abs(noise.mean()) < 0.025
    assert abs(noise.var() - 1.0) < 0.06
    assert noise.mean() != 0.0  # Samples are not forced to fit their own mean.
    if regime == "centered_skew":
        assert noise.min() >= -1.0
        assert noise.max() > 3.0


def test_keyed_stream_reproducible_and_distinct_across_geometry() -> None:
    case = study.scenarios()[0]
    first = study.generated_case(case, 10)
    second = study.generated_case(case, 10)
    for name in first:
        assert_array_equal(first[name], second[name])
    different = study.generated_case(replace(case, base_index=1), 10)
    assert not np.array_equal(first["standardized_noise"], different["standardized_noise"])


@pytest.mark.parametrize("value", [0, -1, 1.2, True])
def test_invalid_trial_count_rejected(value) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        study.generated_case(study.scenarios()[0], value)


@pytest.mark.parametrize("method", study.METHODS)
def test_exact_control_independent_fit_and_no_input_mutation(method: str) -> None:
    data = study.generated_case(study.scenarios()[0], 1)
    _, exact, _ = study.independent_mean(
        data["positions_m"],
        25.0,
        20.0,
        curvature_delay_ns=0.0 if method.startswith("plane") else 80.0,
    )
    original = {name: value.copy() for name, value in data.items()}
    result = study.fit_one(method, data, exact)
    assert result["success"]
    assert result["angular_error_deg"] < 1e-5
    assert result["rms_residual_ns"] < 1e-4
    for name in data:
        assert_array_equal(data[name], original[name])


def test_failure_is_retained_instead_of_zero_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise plane_front.PlaneFrontOptimizationError("intentional numerical failure", ())

    monkeypatch.setattr(plane_front, "fit_plane_front", fail)
    data = study.generated_case(study.scenarios()[0], 1)
    result = study.fit_one("plane_timing", data, data["observed_times_ns"][0])
    assert not result["success"]
    assert result["failure_type"] == "PlaneFrontOptimizationError"
    assert "angular_error_deg" not in result
    assert "intentional" in result["failure_message"]


def test_nested_audit_rejects_violation_and_counts_only_paired_successes() -> None:
    rows = [dict(method=name, success=True, objective_sum_squares=1.0) for name in study.METHODS]
    assert study.audit_nested(rows) == 2
    rows[2]["success"] = False
    assert study.audit_nested(rows) == 1
    rows[3]["objective_sum_squares"] = 4.0
    with pytest.raises(AssertionError, match="Nested objective"):
        study.audit_nested(rows)


def test_bootstrap_is_reproducible_and_resamples_pairs() -> None:
    values = np.array([0.1, 0.2, 0.3])
    assert study.bootstrap_median(values, 15) == study.bootstrap_median(values, 15)
    assert study.bootstrap_median(np.full(10, 0.125), 10) == (0.125, 0.125)
    with pytest.raises(ValueError):
        study.bootstrap_median(np.array([np.nan]), 1)


def test_summary_retains_failure_denominators() -> None:
    case = study.scenarios()[0]
    rows = []
    for trial in range(3):
        for method in study.METHODS:
            success = not (trial == 0 and method == "quadratic_timing")
            rows.append(
                dict(
                    asdict(case),
                    scenario=case.identifier,
                    method=method,
                    trial=trial,
                    success=success,
                    angular_error_deg=0.2 if method.startswith("plane") else 0.1,
                    nominal_reduced_chi_square=1.0,
                    rms_residual_ns=8.0,
                )
            )
    summary, contrasts = study.summarize(pd.DataFrame(rows))
    result = summary[summary.method == "quadratic_timing"].iloc[0]
    assert result.requested == 3
    assert result.successful == 2
    assert result.failed == 1
    paired = contrasts[contrasts.contrast == "curvature_timing"].iloc[0]
    assert paired.paired_successes == 2
    assert paired.unpaired_due_to_failure == 1
    assert paired.median_paired_improvement_deg == pytest.approx(0.1)


def test_entirely_failed_scenario_still_has_explicit_undefined_metrics() -> None:
    case = study.scenarios()[0]
    records = pd.DataFrame(
        [
            dict(asdict(case), scenario=case.identifier, method=method, trial=0, success=False)
            for method in study.METHODS
        ]
    )
    summary, contrasts = study.summarize(records)
    assert (summary.failed == 1).all()
    assert (summary.successful == 0).all()
    assert summary.median_error_deg.isna().all()
    assert (contrasts.paired_successes == 0).all()
    assert (contrasts.unpaired_due_to_failure == 1).all()
    assert contrasts.median_paired_improvement_deg.isna().all()
    assert (contrasts.improvement_tolerance_deg == 1e-5).all()
