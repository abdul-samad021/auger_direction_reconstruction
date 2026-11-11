"""Independent regression checks for evaluation-only direction profiles."""

import numpy as np
import pytest

from auger_reco.evaluation.direction_diagnostics import (
    fit_fixed_direction_quadratic,
    spherical_front_times_ns,
)
from auger_reco.physics.plane_front import C_M_PER_NS, propagation_direction_from_angles


@pytest.fixture
def example():
    rng = np.random.default_rng(219)
    positions = rng.uniform(-1800, 1800, (16, 3))
    positions[:, 2] *= 0.01
    core = np.array([125.0, -320.0, 2.0])
    direction = propagation_direction_from_angles(np.deg2rad(45), np.deg2rad(235))
    offsets = positions - core
    radial_squared = np.sum(np.cross(offsets, direction) ** 2, axis=1)
    times = 1e5 + np.sum(offsets * direction, axis=1) / C_M_PER_NS + 80e-6 * radial_squared
    return positions, times, np.linspace(8, 30, 16), core, direction


@pytest.mark.parametrize("weighting", ["timing", "uniform"])
@pytest.mark.parametrize("epoch", [0, 5e8, -5e8])
def test_exact_fixed_direction_recovery(example, weighting, epoch):
    p, t, s, c, u = example
    fit = fit_fixed_direction_quadratic(p, t + epoch, s, c, u, weighting=weighting)
    assert fit.delay_at_1km_ns == pytest.approx(80, abs=1e-7)
    assert fit.rms_residual_ns < 1e-7
    np.testing.assert_allclose(fit.predict_times_ns(p), t + epoch, rtol=0, atol=2e-7)
    assert fit.nominal_degrees_of_freedom == 14
    assert not fit.residuals_ns.flags.writeable


def test_boundary_refits_intercept(example):
    p, _, s, c, u = example
    offsets = p - c
    rho2 = np.sum(np.cross(offsets, u) ** 2, axis=1)
    t = 1e5 + offsets @ u / C_M_PER_NS - 30e-6 * rho2
    fit = fit_fixed_direction_quadratic(p, t, s, c, u)
    assert fit.curvature_at_boundary
    assert fit.delay_at_1km_ns == 0
    assert np.sum(fit.residuals_ns / s**2) == pytest.approx(0, abs=1e-9)


def test_noisy_fit_agrees_with_independent_design_matrix(example):
    p, t, s, c, u = example
    t = t + np.random.default_rng(332).normal(0, s)
    fit = fit_fixed_direction_quadratic(p, t, s, c, u)
    x = np.column_stack((np.ones(len(t)), np.sum(np.cross(p - c, u) ** 2, axis=1) / 1e6))
    target = t - (p - c) @ u / C_M_PER_NS
    expected = np.linalg.lstsq(x / s[:, None], target / s, rcond=None)[0]
    assert expected[1] > 0
    np.testing.assert_allclose(
        [fit.time_origin_ns + fit.centered_core_time_ns, fit.delay_at_1km_ns],
        expected,
        rtol=0,
        atol=1e-8,
    )


@pytest.mark.parametrize("bad", [np.nan, np.inf, True, "1", 1 + 2j])
def test_reject_invalid_times(example, bad):
    p, t, s, c, u = example
    t = t.astype(object).tolist()
    t[0] = bad
    with pytest.raises(ValueError):
        fit_fixed_direction_quadratic(p, t, s, c, u)


def test_input_contracts(example):
    p, t, s, c, u = example
    for args in (
        (p, t[:-1], s, c, u),
        (p, t, -s, c, u),
        (p, t, s, c, -u),
        (p, t, s, c, 2 * u),
        (p[:2], t[:2], s[:2], c, u),
    ):
        with pytest.raises(ValueError):
            fit_fixed_direction_quadratic(*args)
    with pytest.raises(ValueError):
        fit_fixed_direction_quadratic(p, t, s, c, u, weighting="signal")


def test_equal_radius_unidentifiable():
    p = np.array([[1.0, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]])
    with pytest.raises(ValueError, match="radii"):
        fit_fixed_direction_quadratic(p, np.arange(4.0), np.ones(4), np.zeros(3), [0.0, 0.0, -1.0])


def test_sphere_matches_independent_distance_and_translation(example):
    p, _, _, c, u = example
    radius = 15000.0
    actual = spherical_front_times_ns(p, u, c, 1e5, radius)
    centre = c - radius * u
    expected = 1e5 + (np.linalg.norm(p - centre, axis=1) - radius) / C_M_PER_NS
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-8)
    shift = np.array([1e6, -2e6, 3e5])
    translated = spherical_front_times_ns(p + shift, u, c + shift, 1e5, radius)
    np.testing.assert_allclose(actual, translated, rtol=0, atol=1e-8)
    assert spherical_front_times_ns(c[None, :], u, c, 1e5, radius)[0] == 1e5


def test_sphere_large_radius_plane_limit(example):
    p, _, _, c, u = example
    actual = spherical_front_times_ns(p, u, c, 0, 1e15)
    np.testing.assert_allclose(actual, (p - c) @ u / C_M_PER_NS, rtol=0, atol=1e-7)
    with pytest.raises(ValueError):
        spherical_front_times_ns(p, u, c, 0, -1)
