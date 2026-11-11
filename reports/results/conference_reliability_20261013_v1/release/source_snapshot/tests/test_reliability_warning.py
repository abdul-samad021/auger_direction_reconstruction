"""Scientific contracts for development locking and fit-only warning policies."""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict, fields, replace

import numpy as np
import pytest

from auger_reco.evaluation import reliability_warning as study


@pytest.fixture
def policy() -> study.WarningPolicy:
    return study.WarningPolicy(1.0, True, "test", "digest", "time")


def row(*, radius=0.5, error=0.2, success=True, boundary=False, split="development"):
    return {
        "split": split,
        "fit_success": success,
        "uncertainty_available": success,
        "curvature_boundary": boundary,
        "major_radius_95_deg": radius,
        "angular_error_deg": error,
    }


def test_runtime_interface_has_no_truth_or_error_input(policy):
    assert {field.name for field in fields(study.WarningFeatures)} == {
        "fit_success",
        "uncertainty_available",
        "curvature_boundary",
        "major_radius_95_deg",
    }
    assert set(inspect.signature(study.warning).parameters) == {"features", "policy"}
    first = row(error=0.01)
    second = row(error=100.0)
    assert study.features(first) == study.features(second)
    assert study.warning(study.features(first), policy) == study.warning(
        study.features(second), policy
    )


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (row(radius=1.0), (False, "unflagged")),
        (row(radius=1.00001), (True, "large_local_uncertainty")),
        (row(success=False), (True, "fit_failure")),
        (row(radius=None), (True, "uncertainty_unavailable")),
        (row(radius=np.nan), (True, "uncertainty_unavailable")),
        (row(radius=np.inf), (True, "uncertainty_unavailable")),
        (row(radius=-1.0), (True, "invalid_uncertainty")),
        (row(boundary=True), (True, "curvature_boundary")),
    ],
)
def test_warning_outputs(values, expected, policy):
    assert study.warning(study.features(values), policy) == expected


@pytest.mark.parametrize("threshold", [np.nan, np.inf, -1, 0])
def test_invalid_policy_threshold_rejected(threshold, policy):
    with pytest.raises(ValueError, match="threshold"):
        study.warning(study.features(row()), replace(policy, threshold_deg=threshold))


def test_scenario_splits_disjoint_in_counts_directions_and_ids():
    development, validation = study.scenarios("development"), study.scenarios("validation")
    assert len(development) == len(validation) == 36
    assert not {s.identifier for s in development} & {s.identifier for s in validation}
    assert not {s.count for s in development} & {s.count for s in validation}
    assert not {(s.zenith_deg, s.azimuth_deg) for s in development} & {
        (s.zenith_deg, s.azimuth_deg) for s in validation
    }
    a, b = study.generate(development[0], 3), study.generate(validation[0], 3)
    assert not np.array_equal(a["seed_sequence"], b["seed_sequence"])
    assert a["positions_m"].shape != b["positions_m"].shape
    assert np.isfinite(a["observed_times_ns"]).all()


def test_validation_rotation_jitter_deterministic_and_not_same_positions():
    case = study.scenarios("validation")[0]
    actual = study.station_positions(case)
    assert np.array_equal(actual, study.station_positions(case))
    unperturbed = study.station_positions(replace(case, split="development"))
    assert not np.allclose(actual, unperturbed)


def test_regimes_paired_noise_and_uncertainty_mismatch_is_not_added_noise():
    matched, asymmetry, wrong_dt = [
        study.generate(case, 10) for case in study.scenarios("development")[:3]
    ]
    assert np.array_equal(matched["standardized_noise"], asymmetry["standardized_noise"])
    assert np.array_equal(matched["standardized_noise"], wrong_dt["standardized_noise"])
    assert np.array_equal(matched["observed_times_ns"], wrong_dt["observed_times_ns"])
    assert np.array_equal(matched["actual_sigma_ns"], wrong_dt["actual_sigma_ns"])
    assert np.array_equal(wrong_dt["reported_dt_ns"], 0.5 * matched["reported_dt_ns"])
    assert not np.allclose(matched["mean_times_ns"], asymmetry["mean_times_ns"])


def test_generator_matches_quadratic_timing_formula_independently():
    data = study.generate(study.scenarios("development")[0], 2)
    displacement = data["positions_m"] - data["core_m"]
    projected = displacement @ data["truth_sky"]
    transverse = np.cross(displacement, data["truth_sky"])
    expected = 100000.0 - projected / 0.299792458 + 200 * np.sum(transverse**2, axis=1) / 1e6
    np.testing.assert_allclose(data["mean_times_ns"], expected, rtol=0, atol=3e-11)


def test_smoke_and_production_random_streams_are_disjoint():
    case = study.scenarios("validation")[0]
    smoke = study.generate(case, 2, smoke=True)
    production = study.generate(case, 2, smoke=False)
    assert not np.array_equal(smoke["seed_sequence"], production["seed_sequence"])
    assert not np.array_equal(smoke["observed_times_ns"], production["observed_times_ns"])


def test_development_selection_and_tie_break():
    # Every bad result has radius2, every good result radius0.1. The largest
    # threshold warning at radius2 is1.5; higher thresholds miss every bad result.
    rows = [row(radius=2, error=2) for _ in range(20)]
    rows += [row(radius=0.1, error=0.1) for _ in range(20)]
    chosen, candidates = study.select_policy(rows, "bytes")
    assert chosen.development_viable
    assert chosen.threshold_deg == 1.5
    assert len(candidates) == len(study.THRESHOLDS_DEG)
    assert chosen.development_records_sha256 == "bytes"


def test_nonviable_rule_is_explicit_not_promoted():
    rows = [row(radius=0.1, error=2) for _ in range(20)]
    rows += [row(radius=10.0, error=0.1) for _ in range(20)]
    chosen, _ = study.select_policy(rows, "bytes")
    assert not chosen.development_viable
    assert "No viable" in chosen.selection_reason


def test_policy_selection_rejects_validation_or_mixed_records():
    with pytest.raises(ValueError, match="development-only"):
        study.select_policy([row(), row(split="validation")], "bytes")
    with pytest.raises(ValueError, match="development-only"):
        study.select_policy([], "bytes")


def test_policy_lock_rejects_mutation(tmp_path, policy):
    target = tmp_path / "policy.json"
    study.write_json(target, asdict(policy))
    expected = study.digest(target)
    assert study.load_policy(target, expected) == policy
    changed = asdict(policy) | {"threshold_deg": 2.0}
    target.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match="changed"):
        study.load_policy(target, expected)


def test_validation_requires_lock_before_any_generation(tmp_path):
    with pytest.raises(ValueError, match="locked policy"):
        study.run_phase(tmp_path, "validation", 1)
    assert not (tmp_path / "validation").exists()


def test_evaluation_accounts_failures_without_fake_true_errors(policy):
    rows = [
        row(radius=2, error=2),  # true positive
        row(radius=2, error=0.5),  # false positive
        row(radius=0.5, error=2),  # missed error
        row(radius=0.5, error=0.1),  # true negative
        row(success=False, error=None),
    ]
    result = study.evaluate(rows, policy)
    assert result["requested"] == 5
    assert result["fit_successes"] == 4
    assert result["fit_failures"] == result["failure_warnings"] == 1
    assert result["warning_fraction"] == 3 / 5
    assert result["retention_fraction"] == 2 / 5
    assert result["sensitivity"] == result["false_warning_rate"] == 0.5
    assert result["unflagged_large_error_risk"] == 0.5
    assert result["false_negative"] == 1
    baseline = study.evaluate(rows, None)
    assert baseline["retention_fraction"] == 4 / 5
    assert baseline["sensitivity"] == 0


def test_wilson_counts_and_undefined_rate():
    assert study.wilson(0, 0) == (None, None, None)
    fraction, low, high = study.wilson(50, 100)
    assert fraction == 0.5
    assert low < 0.5 < high
    with pytest.raises(ValueError):
        study.wilson(2, 1)


def test_pooled_paired_regime_intervals_are_omitted(policy):
    rows = [dict(row(), regime="matched"), dict(row(), regime="underreported_dt")]
    result = study.evaluate(rows, policy)
    assert result["retention_fraction"] == 1
    assert result["retention_fraction_low95"] is None
    assert result["retention_fraction_high95"] is None
    assert "pooled regimes" in result["interval_scope"]


def test_create_only_artifacts_and_output_directory(tmp_path):
    target = tmp_path / "result.json"
    study.write_json(target, {"value": np.nan})
    assert json.loads(target.read_text()) == {"value": None}
    with pytest.raises(FileExistsError):
        study.write_json(target, {})
    with pytest.raises(FileExistsError):
        study.run(tmp_path)


@pytest.mark.parametrize("trials", [0, -1, True, 1.5])
def test_invalid_trial_count(trials):
    with pytest.raises(ValueError, match="positive integer"):
        study.generate(study.scenarios("development")[0], trials)


def test_exact_fit_and_fit_only_uncertainty():
    data = study.generate(study.scenarios("development")[0], 1)
    result = study.fit_one(data, data["mean_times_ns"])
    assert result["fit_success"]
    assert result["uncertainty_available"]
    assert result["angular_error_deg"] < 1e-6
    assert result["major_radius_95_deg"] > 0


def test_typed_fit_failure_retained(monkeypatch):
    def fail(*args, **kwargs):
        raise study.curved_front.QuadraticFrontGeometryError("deliberate test")

    monkeypatch.setattr(study.curved_front, "fit_quadratic_front", fail)
    data = study.generate(study.scenarios("development")[0], 1)
    result = study.fit_one(data, data["mean_times_ns"])
    assert not result["fit_success"]
    assert result["failure_type"] == "QuadraticFrontGeometryError"
    assert "angular_error_deg" not in result


def test_covariance_failure_does_not_discard_successful_fit(monkeypatch, policy):
    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("deliberate covariance failure")

    monkeypatch.setattr(study, "directional_uncertainty", fail)
    data = study.generate(study.scenarios("development")[0], 1)
    result = study.fit_one(data, data["mean_times_ns"])
    assert result["fit_success"]
    assert not result["uncertainty_available"]
    assert result["angular_error_deg"] < 1e-6
    assert study.warning(study.features(result), policy) == (True, "uncertainty_unavailable")
