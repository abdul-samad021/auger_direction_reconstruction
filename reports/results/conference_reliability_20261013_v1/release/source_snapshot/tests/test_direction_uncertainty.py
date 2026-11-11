"""Independent numerical checks for conditional local sky uncertainty."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from auger_reco.evaluation import direction_uncertainty as uncertainty
from auger_reco.physics.curved_front import fit_quadratic_front


@pytest.fixture
def setup_arrays():
    positions, sigma = uncertainty.station_layout("well_spread")
    sky, mean = uncertainty.independent_mean(positions, 25.0, 20.0, False)
    return positions, sigma, sky, mean


@pytest.mark.parametrize("sky", ([0, 0, 1], [1, 0, 0], [0, 1, 0], [-0.6, 0, 0.8]))
def test_basis_orthonormal(sky):
    basis = uncertainty.tangent_basis(sky)
    assert_allclose(basis.T @ basis, np.eye(2), atol=1e-14)
    assert_allclose(basis.T @ sky, 0, atol=1e-14)
    assert not basis.flags.writeable


def test_tangent_jacobian_independent_finite_differences(setup_arrays):
    positions, sigma, sky, _ = setup_arrays
    jacobian, basis = uncertainty.whitened_tangent_jacobian(
        positions, sigma, uncertainty.CORE_M, sky, uncertainty.CURVATURE_NS
    )
    offsets = positions - uncertainty.CORE_M

    def model(parameters):
        time, a, b, delay = parameters
        tangent = basis @ [a, b]
        angle = np.linalg.norm(tangent)
        trial_sky = sky if angle == 0 else np.cos(angle) * sky + np.sin(angle) * tangent / angle
        along = -offsets @ trial_sky
        cross = np.cross(offsets, trial_sky)
        return time + along / 0.299792458 + delay * np.sum(cross**2, axis=1) / 1e6

    initial = np.array([0, 0, 0, uncertainty.CURVATURE_NS], dtype=float)
    numeric = np.empty_like(jacobian)
    for column, step in enumerate([1e-3, 1e-6, 1e-6, 1e-3]):
        delta = np.zeros(4)
        delta[column] = step
        numeric[:, column] = (model(initial + delta) - model(initial - delta)) / (2 * step) / sigma
    assert_allclose(jacobian, numeric, rtol=3e-7, atol=2e-7)


def test_full_covariance_matches_nuisance_projection(setup_arrays):
    positions, sigma, sky, _ = setup_arrays
    result = uncertainty.directional_uncertainty(
        positions, sigma, uncertainty.CORE_M, sky, uncertainty.CURVATURE_NS
    )
    jacobian, _ = uncertainty.whitened_tangent_jacobian(
        positions, sigma, uncertainty.CORE_M, sky, uncertainty.CURVATURE_NS
    )
    nuisance = jacobian[:, [0, 3]]
    q, _ = np.linalg.qr(nuisance)
    angular = jacobian[:, 1:3]
    residualized = angular - q @ (q.T @ angular)
    expected = np.linalg.solve(residualized.T @ residualized, np.eye(2))
    assert result.available
    assert_allclose(result.covariance_rad2, expected, rtol=1e-12, atol=1e-20)


def test_known_sigma_scaling_not_residual_rescaling(setup_arrays):
    positions, sigma, sky, _ = setup_arrays
    first = uncertainty.directional_uncertainty(positions, sigma, uncertainty.CORE_M, sky, 200)
    second = uncertainty.directional_uncertainty(positions, sigma * 2, uncertainty.CORE_M, sky, 200)
    assert_allclose(second.covariance_rad2, first.covariance_rad2 * 4, rtol=1e-13)
    assert_allclose(second.major_radius_95_deg, first.major_radius_95_deg * 2, rtol=1e-13)


@pytest.mark.parametrize("method", ["svd", "eigvalsh"])
def test_numerical_covariance_failure_is_explicitly_unavailable(setup_arrays, monkeypatch, method):
    positions, sigma, sky, _ = setup_arrays

    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("deliberate test failure")

    monkeypatch.setattr(np.linalg, method, fail)
    result = uncertainty.directional_uncertainty(positions, sigma, uncertainty.CORE_M, sky, 200)
    assert not result.available
    assert result.covariance_rad2 is None


def test_covariance_invariant_to_common_translation(setup_arrays):
    positions, sigma, sky, _ = setup_arrays
    shift = np.array([12340.0, -555000.0, 1600.0])
    first = uncertainty.directional_uncertainty(positions, sigma, uncertainty.CORE_M, sky, 200)
    second = uncertainty.directional_uncertainty(
        positions + shift, sigma, uncertainty.CORE_M + shift, sky, 200
    )
    assert_allclose(second.covariance_rad2, first.covariance_rad2, rtol=1e-12)


def test_boundary_is_flag_not_calibration_guarantee(setup_arrays):
    positions, sigma, sky, _ = setup_arrays
    result = uncertainty.directional_uncertainty(positions, sigma, uncertainty.CORE_M, sky, 0)
    assert result.available
    assert "curvature_boundary" in result.quality_flags


def test_rank_deficient_timing_information_is_unavailable():
    positions = np.column_stack((np.arange(8.0), np.zeros(8), np.zeros(8)))
    result = uncertainty.directional_uncertainty(positions, np.ones(8), np.zeros(3), [0, 0, 1], 200)
    assert not result.available
    assert result.covariance_rad2 is None
    assert result.major_radius_95_deg is None


@pytest.mark.parametrize("angle", [0.0, 1e-12, 0.1, 2.0])
def test_spherical_log_map_recovers_great_circle_distance(angle):
    fitted = np.array([0.0, 0.0, 1.0])
    basis = uncertainty.tangent_basis(fitted)
    truth = np.cos(angle) * fitted + np.sin(angle) * basis[:, 0]
    displacement = uncertainty.log_map_components(fitted, truth, basis)
    assert_allclose(displacement, [angle, 0], atol=1e-14)


def test_log_map_antipode_is_undefined():
    with pytest.raises(ValueError, match="antipode"):
        uncertainty.log_map_components([0, 0, 1], [0, 0, -1], uncertainty.tangent_basis([0, 0, 1]))


def test_exact_known_truth_inside_region(setup_arrays):
    positions, sigma, sky, mean = setup_arrays
    fit = fit_quadratic_front(positions, mean, sigma, core_position_m=uncertainty.CORE_M)
    region = uncertainty.directional_uncertainty(
        positions, sigma, uncertainty.CORE_M, fit.sky_direction, fit.delay_at_1km_ns
    )
    assert uncertainty.squared_direction_distance(region, fit.sky_direction, sky) < 1e-12


@pytest.mark.parametrize("change", ["nan", "bad_shape", "zero_sigma", "complex", "negative_delay"])
def test_invalid_inputs_fail_explicitly(setup_arrays, change):
    positions, sigma, sky, _ = setup_arrays
    delay = 200.0
    if change == "nan":
        positions[0, 0] = np.nan
    elif change == "bad_shape":
        positions = positions[:, :2]
    elif change == "zero_sigma":
        sigma[0] = 0
    elif change == "complex":
        positions = positions.astype(complex)
    else:
        delay = -1.0
    with pytest.raises(ValueError):
        uncertainty.directional_uncertainty(positions, sigma, uncertainty.CORE_M, sky, delay)


def test_wilson_interval_edges():
    lower, upper = uncertainty.wilson_interval(0, 200)
    assert lower == pytest.approx(0, abs=1e-15)
    assert 0.01 < upper < 0.02
    lower, upper = uncertainty.wilson_interval(200, 200)
    assert 0.98 < lower < 0.99
    assert upper == pytest.approx(1)
    assert uncertainty.wilson_interval(0, 0) == (None, None)
    with pytest.raises(ValueError):
        uncertainty.wilson_interval(3, 2)


def test_paired_ring_has_identical_retained_measurement_geometry():
    ring, sigma = uncertainty.station_layout("ring_no_anchor")
    anchor, anchor_sigma = uncertainty.station_layout("ring_anchor")
    assert_allclose(anchor[:-1], ring, atol=0)
    assert_allclose(anchor_sigma[:-1], sigma, atol=0)
