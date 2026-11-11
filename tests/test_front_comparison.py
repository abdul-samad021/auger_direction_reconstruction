"""Regression tests for conditional real-event front comparisons."""

import json
from dataclasses import replace

import numpy as np
import pytest

from auger_reco.evaluation import front_comparison as comparison
from auger_reco.physics.curved_front import QuadraticFrontFitOptions
from auger_reco.physics.plane_front import (
    OptimizerAttempt,
    PlaneFrontFitOptions,
    PlaneFrontOptimizationError,
    angular_separation_deg,
    propagation_direction_from_angles,
)
from auger_reco.physics.quadratic_front import quadratic_front_times_ns


@pytest.fixture
def measurements():
    rng = np.random.default_rng(4121)
    positions = rng.uniform(-1_200.0, 1_200.0, size=(10, 3))
    positions[:, 2] *= 0.01
    direction = propagation_direction_from_angles(np.deg2rad(42.0), np.deg2rad(125.0))
    core = np.array([180.0, -200.0, 3.0])
    times = quadratic_front_times_ns(positions, direction, core, 100_000.0, 80.0 / 1e6)
    return {
        "positions_m": positions,
        "times_ns": times,
        "uncertainties_ns": np.linspace(8.0, 16.0, 10),
        "core_position_m": core,
        "station_ids": [f"S{i}" for i in range(10)],
    }, direction


def quick_comparison(values, **kwargs):
    settings = {"run_leave_one_out": False, "core_offsets_m": np.empty((0, 3))}
    settings.update(kwargs)
    return comparison.compare_event_fronts(**values, **settings)


@pytest.mark.parametrize("delay", [0.0, 80.0])
def test_exact_full_recovery_and_prediction_agreement(measurements, delay):
    values, direction = measurements
    values["times_ns"] = quadratic_front_times_ns(
        values["positions_m"], direction, values["core_position_m"], 100_000.0, delay / 1e6
    )
    saved_positions = values["positions_m"].copy()
    saved_times = values["times_ns"].copy()
    result = quick_comparison(values)
    assert len(result.records) == 4
    assert all(row["success"] for row in result.records)
    assert len(result.station_residuals) == 40
    assert not result.configuration["reference_direction_used"]
    for (model, weighting), fit in result.full_fits.items():
        prediction = comparison.predict_fit_times_ns(fit, values["positions_m"])
        np.testing.assert_allclose(prediction, fit.predicted_times_ns, rtol=0, atol=1e-8)
        if model == "quadratic" or delay == 0.0:
            assert angular_separation_deg(fit.propagation_direction, direction) < 1e-6
            np.testing.assert_allclose(prediction, values["times_ns"], rtol=0, atol=1e-5)
        if model == "quadratic":
            assert fit.delay_at_1km_ns == pytest.approx(delay, abs=1e-4)
            row = next(
                row
                for row in result.records
                if row["model"] == model and row["weighting"] == weighting
            )
            assert not row["nested_objective_violation"]
            assert row["nominal_degrees_of_freedom"] == 6
    np.testing.assert_array_equal(values["positions_m"], saved_positions)
    np.testing.assert_array_equal(values["times_ns"], saved_times)
    assert result.optimizer_attempts
    for row in result.optimizer_attempts:
        assert "final_parameters" in row
        assert "optimality" in row
        assert "function_evaluations" in row
    json.dumps(result.records, allow_nan=False)
    json.dumps(result.configuration, allow_nan=False)


def test_leave_one_out_really_excludes_held_out_measurement(measurements):
    values, _ = measurements
    initial = quick_comparison(values, run_leave_one_out=True)
    changed = dict(values)
    changed["times_ns"] = values["times_ns"].copy()
    changed["times_ns"][0] += 1_000.0
    perturbed = quick_comparison(changed, run_leave_one_out=True)
    assert len(initial.records) == 44
    assert len(initial.station_residuals) == 80
    for model in ("plane", "quadratic"):
        for weighting in ("timing", "uniform"):

            def selected_record(output, model=model, weighting=weighting):
                return next(
                    row
                    for row in output.station_residuals
                    if row["stage"] == "leave_one_out"
                    and row["station_index"] == 0
                    and row["model"] == model
                    and row["weighting"] == weighting
                )

            before = selected_record(initial)
            after = selected_record(perturbed)
            assert after["predicted_time_ns"] == before["predicted_time_ns"]
            assert after["residual_ns"] - before["residual_ns"] == pytest.approx(1_000.0)
            assert after["residual_over_observed_sigma"] == pytest.approx(
                after["residual_ns"] / values["uncertainties_ns"][0]
            )
            assert before["residual_kind"] == "held_out"
            assert before["held_out_station_id"] == "S0"
    assert all(
        row["number_of_stations"] == 9 for row in initial.records if row["stage"] == "leave_one_out"
    )


def test_leave_one_out_uses_fit_owned_reference_and_core(measurements):
    values, direction = measurements
    result = quick_comparison(values, run_leave_one_out=True)
    for row in result.station_residuals:
        if row["stage"] == "leave_one_out" and row["model"] == "quadratic":
            assert abs(row["residual_ns"]) < 1e-4
            index = row["station_index"]
            expected_distance = np.linalg.norm(
                np.cross(values["positions_m"][index] - values["core_position_m"], direction)
            )
            assert row["axis_distance_m"] == pytest.approx(expected_distance, abs=1e-5)


def test_default_core_sensitivity_and_configuration(measurements):
    values, _ = measurements
    plane_options = replace(PlaneFrontFitOptions(), maximum_function_evaluations=800)
    curved_options = replace(QuadraticFrontFitOptions(), maximum_function_evaluations=900)
    result = comparison.compare_event_fronts(
        **values,
        run_leave_one_out=False,
        plane_options=plane_options,
        curved_options=curved_options,
    )
    rows = [row for row in result.records if row["stage"] == "core_shift"]
    assert len(rows) == 4
    assert all(row["model"] == "quadratic" and row["weighting"] == "timing" for row in rows)
    assert all(row["direction_shift_from_full_deg"] > 0 for row in rows)
    assert result.configuration["plane_options"]["maximum_function_evaluations"] == 800
    assert result.configuration["curved_options"]["maximum_function_evaluations"] == 900


def test_known_failure_and_optimizer_metadata_retained(measurements, monkeypatch):
    values, _ = measurements
    attempt = OptimizerAttempt(
        initializer="test",
        accepted=False,
        scipy_success=False,
        status=0,
        message="evaluation limit",
        objective_sum_squares=200.0,
        scipy_cost=100.0,
        optimality=1.0,
        function_evaluations=3,
        jacobian_evaluations=2,
        active_mask=(0, 0, 0),
        final_parameters=(1.0, 2.0, 3.0),
        exception_type=None,
    )

    def failed(*args, **kwargs):
        raise PlaneFrontOptimizationError("controlled failure", (attempt,))

    monkeypatch.setattr(comparison, "fit_plane_front", failed)
    result = quick_comparison(values)
    failed_rows = [row for row in result.records if not row["success"]]
    assert len(failed_rows) == 2
    assert len(result.full_fits) == 2
    for row in failed_rows:
        assert row["failure_type"] == "PlaneFrontOptimizationError"
        assert row["failure_message"] == "controlled failure"
        assert row["chi_square"] is None
        assert row["delay_at_1km_ns"] is None
    retained = [row for row in result.optimizer_attempts if row["model"] == "plane"]
    assert len(retained) == 2
    assert retained[0]["final_parameters"] == (1.0, 2.0, 3.0)
    assert retained[0]["status"] == 0


def test_unexpected_error_is_not_silenced(measurements, monkeypatch):
    values, _ = measurements

    def programming_error(*args, **kwargs):
        raise KeyError("programming defect")

    monkeypatch.setattr(comparison, "fit_plane_front", programming_error)
    with pytest.raises(KeyError, match="programming defect"):
        quick_comparison(values)


def test_degenerate_geometry_is_recorded_not_removed(measurements):
    values, _ = measurements
    values["positions_m"] = np.column_stack((np.arange(10), np.zeros((10, 2))))
    result = quick_comparison(values)
    assert len(result.records) == 4
    assert not result.full_fits
    assert all(not row["success"] for row in result.records)
    assert all(row["failure_type"] is not None for row in result.records)


def test_insufficient_fold_stations_are_explicit_failures(measurements):
    values, _ = measurements
    for key in ("positions_m", "times_ns", "uncertainties_ns", "station_ids"):
        values[key] = values[key][:6]
    result = quick_comparison(values, run_leave_one_out=True)
    skipped = [row for row in result.records if row["failure_type"] == "InsufficientStations"]
    assert len(skipped) == 12
    assert all(row["stage"] == "leave_one_out" and row["model"] == "quadratic" for row in skipped)
    assert all(row["number_of_stations"] == 5 for row in skipped)


@pytest.mark.parametrize(
    "key,bad",
    [
        ("positions_m", np.ones((10, 2))),
        ("positions_m", np.full((10, 3), np.nan)),
        ("positions_m", np.ones((10, 3), dtype=bool)),
        ("times_ns", np.ones((10, 1))),
        ("times_ns", np.full(10, np.inf)),
        ("uncertainties_ns", np.zeros(10)),
        ("uncertainties_ns", np.full(10, -1.0)),
        ("core_position_m", np.ones(2)),
        ("station_ids", ["same"] * 10),
        ("station_ids", list(range(9))),
        ("station_ids", [True] * 10),
        ("station_ids", "stationids"),
    ],
)
def test_invalid_inputs_rejected_before_fitting(measurements, key, bad):
    values, _ = measurements
    values[key] = bad
    with pytest.raises(ValueError):
        quick_comparison(values)


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"core_offsets_m": [1.0, 2.0, 3.0]}, ValueError),
        ({"core_offsets_m": [[0.0, np.inf, 0.0]]}, ValueError),
        ({"run_leave_one_out": 1}, TypeError),
        ({"plane_options": {}}, TypeError),
        ({"curved_options": {}}, TypeError),
        ({"plane_options": PlaneFrontFitOptions(optimizer_loss="soft_l1")}, ValueError),
    ],
)
def test_invalid_configuration_rejected(measurements, kwargs, error):
    values, _ = measurements
    with pytest.raises(error):
        quick_comparison(values, **kwargs)


def test_prediction_requires_known_fit_type():
    with pytest.raises(TypeError, match="plane or quadratic"):
        comparison.predict_fit_times_ns(None, np.zeros((1, 3)))
