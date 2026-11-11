"""Independent algebra, derivative, selection and boundary checks for the audit."""

import json
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from auger_reco.evaluation import conference_instability as study
from auger_reco.physics import curved_front, plane_front


def test_explicit_existing_output_is_refused(tmp_path):
    output = tmp_path / "fresh_named_study"
    output.mkdir()
    with pytest.raises(FileExistsError):
        study.run(tmp_path, output_directory=output)


def test_ablation_uses_explicit_output_receipt(tmp_path):
    output = tmp_path / "fresh_named_study"
    output.mkdir()
    (output / "completion.json").write_text(
        json.dumps({"artifact_hashes": {"nonexistent.json": "invalid"}})
    )
    with pytest.raises(FileNotFoundError) as caught:
        study.run_anchor_ablation(tmp_path, output_directory=output)
    assert "nonexistent.json" in str(caught.value)


@pytest.fixture
def example():
    rng = np.random.default_rng(61013)
    positions = rng.uniform(-1500, 1500, size=(10, 3))
    positions[:, 2] *= 0.015
    core = np.array([120, -80, 10.0])
    sky = plane_front.sky_direction_from_angles(np.deg2rad(43), np.deg2rad(219))
    sigma = np.linspace(8, 30, len(positions))
    displacement = positions - core
    along = displacement @ (-sky)
    transverse = displacement - along[:, None] * (-sky)
    times = 1e6 + along / plane_front.C_M_PER_NS + 85 * np.sum(transverse**2, axis=1) / 1e6
    return positions, times, sigma, core, sky


def test_profile_recovers_time_and_curvature(example):
    result = study.profile_direction(*example)
    assert result["delay_at_1km_ns"] == pytest.approx(85.0, abs=1e-9)
    assert result["centered_core_time_ns"] + result["time_origin_ns"] == pytest.approx(
        1e6, abs=1e-8
    )
    assert result["objective_sum_squares"] < 1e-18


def test_profile_zero_boundary_is_correct_convex_solution(example):
    p, _, sigma, core, sky = example
    along = (p - core) @ (-sky)
    radii2 = np.sum(np.cross(p - core, sky) ** 2, axis=1)
    times = 1000 + along / plane_front.C_M_PER_NS - 50 * radii2 / 1e6
    result = study.profile_direction(p, times, sigma, core, sky)
    assert result["delay_at_1km_ns"] == 0
    weights = 1 / sigma**2
    expected = np.average(times - along / plane_front.C_M_PER_NS, weights=weights)
    assert result["centered_core_time_ns"] + times[0] == pytest.approx(expected)


def test_independent_profile_agrees_with_public_fit(example):
    p, times, sigma, core, _ = example
    noisy = times + np.random.default_rng(6).normal(size=len(times)) * sigma
    fitted = curved_front.fit_quadratic_front(p, noisy, sigma, core_position_m=core)
    profiled = study.profile_direction(p, noisy, sigma, core, fitted.sky_direction)
    assert profiled["objective_sum_squares"] == pytest.approx(
        fitted.objective_sum_squares, rel=1e-8, abs=1e-8
    )


def test_profile_epoch_translation(example):
    p, times, sigma, core, sky = example
    baseline = study.profile_direction(*example)
    shifted = study.profile_direction(p, times + 1e8, sigma, core, sky)
    np.testing.assert_allclose(baseline["residuals_ns"], shifted["residuals_ns"], atol=2e-8)


def test_analytic_augmented_jacobian_matches_finite_difference(example):
    p, _, sigma, core, sky = example
    parameters = np.array([2000, *(sky[:2] / sky[2]), 85, 35, -20])
    diagnostics = study.jacobian_diagnostics(parameters, p, core, sigma)
    assert diagnostics["central_difference_max_scaled_error"] < 2e-7
    assert diagnostics["fixed_core_rank"] == 4
    assert np.sum(diagnostics["fixed_core_local_leverage"]) == pytest.approx(4)
    assert diagnostics["augmented_core_xy_condition"] >= diagnostics["fixed_core_condition"]


def test_derivative_model_matches_cross_product_generation(example):
    p, times, _, core, sky = example
    parameters = np.array([1e6, *(sky[:2] / sky[2]), 85, 0, 0])
    predicted, _ = study.prediction_and_jacobian(parameters, p, core)
    np.testing.assert_allclose(predicted, times, atol=1e-9, rtol=0)


def test_independent_multistart_recovers_exact_direction(example):
    p, times, sigma, core, sky = example
    attempts = study.independent_multistart(p, times, sigma, core, [sky, sky])
    assert len(attempts) == 14
    successful = [attempt for attempt in attempts if attempt["success"]]
    assert successful
    best = min(successful, key=lambda item: item["objective_sum_squares"])
    assert best["objective_sum_squares"] < 1e-16
    assert plane_front.angular_separation_deg(best["sky_direction"], sky) < 1e-8


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf])
def test_profile_rejects_invalid_sigma(example, bad):
    p, times, sigma, core, sky = example
    sigma[0] = bad
    with pytest.raises(ValueError):
        study.profile_direction(p, times, sigma, core, sky)


def test_profile_rejects_misaligned_input(example):
    p, times, sigma, core, sky = example
    with pytest.raises(ValueError):
        study.profile_direction(p, times[:-1], sigma, core, sky)


@pytest.mark.parametrize("sky", [[0, 0, -1], [0, 0, 2], [1, 0, 0]])
def test_profile_rejects_nonphysical_direction(example, sky):
    p, times, sigma, core, _ = example
    with pytest.raises(ValueError):
        study.profile_direction(p, times, sigma, core, sky)


def test_profile_rejects_equal_radius_geometry():
    p = np.array([[1.0, 0, 0], [-1, 0, 0], [0, 1, 0]])
    with pytest.raises(ValueError, match="identify"):
        study.profile_direction(p, np.zeros(3), np.ones(3), np.zeros(3), [0.0, 0, 1])


def test_spherical_profile_includes_endpoints_and_stays_unit(example):
    sky = example[-1]
    other = plane_front.sky_direction_from_angles(0.9, 0.3)
    path = study.spherical_path(sky, other)
    np.testing.assert_allclose(np.linalg.norm(path, axis=1), 1.0, atol=1e-14)
    np.testing.assert_allclose(path[[0, -1]], [sky, other], atol=1e-14)
    assert np.all(path[:, 2] > 0)


def test_identical_spherical_endpoints(example):
    path = study.spherical_path(example[-1], example[-1])
    np.testing.assert_allclose(path, np.tile(example[-1], (101, 1)), atol=1e-14)


def selection_fixture():
    rows = []
    for index, influence in enumerate([18, 14, 12, 0.1, 0.2, 0.3, 0.4, 0.5]):
        rows.append(
            dict(
                event_id=f"{index:012d}",
                model="quadratic",
                weighting="timing",
                number_of_stations=7,
                full_success=True,
                heldout_complete=True,
                maximum_loo_direction_shift_deg=influence,
                reduced_chi_square=index + 1,
            )
        )
    return pd.DataFrame(rows)


def test_selection_deterministic_under_row_order_and_overlap():
    metrics = selection_fixture()
    chosen = study.select_cases(metrics)
    shuffled = study.select_cases(metrics.sample(frac=1, random_state=8))
    pd.testing.assert_frame_equal(chosen, shuffled)
    assert set(chosen.event_id) == {f"{i:012d}" for i in (0, 1, 2, 5, 6, 7)}
    assert (
        chosen.loc[chosen.event_id == "000000000005", "selection_roles"].item()
        == "matched_stable_median"
    )


def test_selection_does_not_consume_reference_angles():
    first = selection_fixture()
    second = first.assign(separation_from_auger_deg=np.arange(len(first))[::-1])
    assert list(study.select_cases(first).event_id) == list(study.select_cases(second).event_id)


def test_selection_excludes_incomplete_six_station_cases():
    metrics = selection_fixture()
    metrics.loc[0, "number_of_stations"] = 6
    metrics.loc[0, "heldout_complete"] = False
    assert "000000000000" not in set(study.select_cases(metrics).event_id)


def test_selection_rejects_duplicate_event():
    metrics = selection_fixture()
    with pytest.raises(ValueError, match="unique"):
        study.select_cases(pd.concat([metrics, metrics.iloc[:1]]))


def test_receipt_digest_verified_and_tamper_rejected(tmp_path):
    payload = {"event_id": "example", "objective": 1.0}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    target = tmp_path / "receipt.json"
    target.write_text(json.dumps({"payload": payload, "sha256": sha256(encoded).hexdigest()}))
    assert study._archived_payload(target) == payload
    payload["objective"] = 2.0
    target.write_text(json.dumps({"payload": payload, "sha256": sha256(encoded).hexdigest()}))
    with pytest.raises(RuntimeError, match="hash"):
        study._archived_payload(target)


def test_existing_run_is_never_overwritten(tmp_path):
    (tmp_path / study.OUTPUT).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        study.run(tmp_path)


def test_paired_bootstrap_preserves_exact_constant_increase():
    full = np.linspace(0.01, 0.2, 200)
    summary = study.paired_ablation_summary(full, full + 2)
    assert summary["median_paired_error_increase_deg"] == pytest.approx(2)
    assert summary["paired_median_increase_ci95_low_deg"] == pytest.approx(2)
    assert summary["paired_median_increase_ci95_high_deg"] == pytest.approx(2)
    assert summary["full_error_above_1deg_fraction"] == 0
    assert summary["omitted_error_above_1deg_fraction"] == 1


def test_paired_bootstrap_reproducible_and_threshold_strict():
    full = np.linspace(0.1, 0.3, 200)
    omitted = np.ones(200)
    first = study.paired_ablation_summary(full, omitted)
    second = study.paired_ablation_summary(full, omitted)
    assert first == second
    assert first["omitted_error_above_1deg_fraction"] == 0


@pytest.mark.parametrize("full, omitted", [([0], [1]), ([0, 1], [1]), ([0, -1], [1, 2])])
def test_paired_bootstrap_rejects_invalid_pairs(full, omitted):
    with pytest.raises(ValueError):
        study.paired_ablation_summary(full, omitted)
