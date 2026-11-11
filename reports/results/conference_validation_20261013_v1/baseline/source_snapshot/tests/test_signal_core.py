"""Experimental signal-core controls; no real-event answer is a test oracle."""

import numpy as np
import pytest

from auger_reco.physics import signal_core as module
from auger_reco.physics.plane_front import propagation_direction_from_angles


@pytest.fixture
def example():
    rng = np.random.default_rng(583)
    positions = rng.uniform(-1800, 1800, (20, 3))
    positions[:, 2] *= 0.005
    core = np.array([230.0, -135.0, 3.0])
    direction = propagation_direction_from_angles(np.deg2rad(42), np.deg2rad(65))
    options = module.SignalCoreFitOptions(beta=-3, gamma=1)
    # Independently express the radial model; do not use the predictor to generate.
    rho = np.linalg.norm(np.cross(positions - core, direction), axis=1)
    radius = np.sqrt(rho**2 + 1)
    reference = np.sqrt(1000**2 + 1)
    signals = 100 * (radius / reference) ** -3 * ((radius + 700) / (reference + 700)) ** -2
    return positions, core, direction, options, signals


def run(example, **kwargs):
    p, c, u, options, signal = example
    arguments = dict(propagation_direction=u, core_z_m=c[2], options=options)
    arguments.update(kwargs)
    return module.fit_signal_core(p, signal, signal * 0.1, **arguments)


def test_known_core_recovery_and_independent_predictions(example):
    p, c, u, options, signals = example
    fit = run(example)
    np.testing.assert_allclose(fit.core_position_m, c, atol=1e-5, rtol=0)
    assert fit.s1000_vem == pytest.approx(100, abs=1e-6)
    np.testing.assert_allclose(fit.predicted_signals_vem, signals, rtol=1e-8)
    assert fit.final_jacobian_rank == 3
    assert fit.objective_sum_squares < 1e-14
    assert len(fit.optimizer_attempts) == 5
    assert not fit.core_position_m.flags.writeable
    assert "experimental_fixed_shape" in fit.quality_flags
    np.testing.assert_allclose(module.predict_signals_vem(p, u, c, 100, options=options), signals)


def test_translation_and_signal_scaling(example):
    p, c, u, options, s = example
    fit = run(example)
    translation = np.array([1e6, -3e6, 1e4])
    shifted = run((p + translation, c + translation, u, options, s * 12))
    np.testing.assert_allclose(
        shifted.core_position_m - translation, fit.core_position_m, rtol=0, atol=1e-4
    )
    assert shifted.s1000_vem == pytest.approx(12 * fit.s1000_vem, rel=1e-7)


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf])
def test_invalid_signal_values(example, bad):
    p, c, u, options, signals = example
    signals = signals.copy()
    signals[0] = bad
    with pytest.raises(ValueError):
        run((p, c, u, options, signals))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"beta": 1},
        {"gamma": 5},
        {"radial_softening_m": 0},
        {"minimum_stations": True},
        {"optimizer_tolerance": 0},
        {"beta": "-3"},
        {"gamma": np.nan},
        {"condition_warning_threshold": 1},
    ],
)
def test_invalid_options(kwargs):
    values = {"beta": -3, "gamma": 1, **kwargs}
    with pytest.raises(ValueError):
        module.SignalCoreFitOptions(**values)


def test_degenerate_layout_and_shapes(example):
    p, c, u, options, signals = example
    with pytest.raises(ValueError):
        run((p[:-1], c, u, options, signals))
    p = np.column_stack((np.arange(20.0), np.zeros((20, 2))))
    with pytest.raises(ValueError, match="span"):
        run((p, c, u, options, signals))


def test_numerical_optimizer_failure_retains_each_seed(example, monkeypatch):
    def failing(*args, **kwargs):
        raise FloatingPointError("test failure")

    monkeypatch.setattr(module, "least_squares", failing)
    with pytest.raises(module.SignalCoreOptimizationError) as raised:
        run(example)
    assert len(raised.value.attempts) == 5
    assert all(row["exception"] == "FloatingPointError" for row in raised.value.attempts)


def test_inputs_not_modified(example):
    p, c, u, _, signals = example
    copies = [a.copy() for a in (p, c, u, signals)]
    run(example)
    for value, before in zip((p, c, u, signals), copies, strict=True):
        np.testing.assert_array_equal(value, before)
