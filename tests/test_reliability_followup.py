"""Independent tangent information replay and its numerical invariances."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_reliability_followup.py"
SPEC = importlib.util.spec_from_file_location("audit_reliability_followup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def geometry():
    rng = np.random.default_rng(571)
    positions = rng.normal(size=(13, 3)) * [1300, 800, 15]
    sigma = np.linspace(8, 20, 13)
    core = np.array([120.0, -80.0, 0.0])
    sky = np.array([0.3, 0.4, np.sqrt(0.75)])
    return positions, sigma, core, sky


def test_information_replay_is_tangent_positive_and_scales_with_sigma():
    positions, sigma, core, sky = geometry()
    result = audit.replay_covariance(positions, sigma, core, sky, 80.0)
    np.testing.assert_allclose(result @ sky, 0, atol=1e-17)
    assert np.linalg.eigvalsh(result)[-2] > 0
    doubled = audit.replay_covariance(positions, sigma * 2, core, sky, 80.0)
    np.testing.assert_allclose(doubled, result * 4, rtol=1e-12, atol=1e-17)


def test_information_replay_is_translation_and_rotation_invariant():
    positions, sigma, core, sky = geometry()
    baseline = audit.replay_covariance(positions, sigma, core, sky, 80.0)
    offset = np.array([2e5, -3e5, 700])
    shifted = audit.replay_covariance(positions + offset, sigma, core + offset, sky, 80.0)
    np.testing.assert_allclose(shifted, baseline, rtol=1e-11, atol=1e-15)
    angle = 0.63
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]]
    )
    rotated = audit.replay_covariance(
        positions @ rotation.T, sigma, rotation @ core, rotation @ sky, 80.0
    )
    np.testing.assert_allclose(rotated, rotation @ baseline @ rotation.T, atol=1e-15)


def test_qr_information_matches_independent_finite_difference_jacobian():
    positions, sigma, core, sky = geometry()
    basis = audit.tangent_basis(sky)
    offsets = positions - core

    def times(direction, curvature):
        return (
            -offsets @ direction / 0.299792458
            + curvature * np.sum(np.cross(offsets, direction) ** 2, axis=1) / 1e6
        )

    step = 1e-5
    angular = [
        (
            times(np.cos(step) * sky + np.sin(step) * column, 80)
            - times(np.cos(step) * sky - np.sin(step) * column, 80)
        )
        / (2 * step)
        for column in basis.T
    ]
    derivative_a = (times(sky, 80 + step) - times(sky, 80 - step)) / (2 * step)
    jacobian = np.column_stack((np.ones(len(sigma)), *angular, derivative_a)) / sigma[:, None]
    # Independent test-only pseudoinverse; full rank is checked explicitly.
    assert np.linalg.matrix_rank(jacobian) == 4
    pseudoinverse = np.linalg.pinv(jacobian)
    covariance = pseudoinverse @ pseudoinverse.T
    expected = basis @ covariance[1:3, 1:3] @ basis.T
    replay = audit.replay_covariance(positions, sigma, core, sky, 80)
    np.testing.assert_allclose(replay, expected, rtol=1e-6, atol=1e-13)


def test_sphere_log_uses_geodesic_not_projected_chord():
    sky = np.array([0.0, 0.0, 1.0])
    angle = 0.2
    truth = np.array([np.sin(angle), 0, np.cos(angle)])
    covariance = np.diag([0.01, 0.04, 0])
    assert audit.replay_mahalanobis(sky, truth, covariance) == pytest.approx(4)
    assert audit.replay_angular_error_deg(sky, truth) == pytest.approx(np.rad2deg(angle))
    assert audit.replay_mahalanobis(sky, sky, covariance) == 0
    with pytest.raises(ValueError, match="Antipodal"):
        audit.replay_mahalanobis(sky, -sky, covariance)


@pytest.mark.parametrize("kind", ["zero_sigma", "nan", "shape", "negative_a", "zero_sky"])
def test_invalid_inputs_do_not_produce_apparently_valid_covariance(kind):
    positions, sigma, core, sky = geometry()
    curvature = 80
    if kind == "zero_sigma":
        sigma[0] = 0
    elif kind == "nan":
        positions[0, 0] = np.nan
    elif kind == "shape":
        positions = positions[:, :2]
    elif kind == "negative_a":
        curvature = -1
    else:
        sky[:] = 0
    with pytest.raises(ValueError):
        audit.replay_covariance(positions, sigma, core, sky, curvature)


def test_rank_deficient_nuisance_is_rejected():
    angle = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    positions = np.column_stack((1000 * np.cos(angle), 1000 * np.sin(angle), np.zeros(8)))
    with pytest.raises(ValueError, match="nuisance"):
        audit.replay_covariance(positions, np.ones(8), np.zeros(3), [0, 0, 1], 80)


def test_wilson_known_values_and_invalid_denominator():
    low, high = audit.wilson_interval(95, 100)
    assert low == pytest.approx(0.8882495307680809)
    assert high == pytest.approx(0.978456320845632)
    assert audit.wilson_interval(0, 100)[0] == 0
    with pytest.raises(ValueError):
        audit.wilson_interval(1, 0)
