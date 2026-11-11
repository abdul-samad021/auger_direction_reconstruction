"""Analytic and invariance checks for the controlled quadratic timing model."""

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from auger_reco.physics.plane_front import C_M_PER_NS, predict_station_times_ns
from auger_reco.physics.quadratic_front import quadratic_front_times_ns


@pytest.fixture
def inputs() -> dict:
    """A nontrivial tilted geometry with an independently specified unit vector."""
    return {
        "station_positions_m": np.array(
            [[100.0, 300.0, 10.0], [-700.0, 400.0, -20.0], [350.0, -200.0, 5.0]]
        ),
        "propagation_direction": np.array([0.3, 0.4, -np.sqrt(0.75)]),
        "core_position_m": np.array([40.0, -60.0, 5.0]),
        "core_time_ns": 10_000.0,
        "curvature_ns_per_m2": 1.0e-4,
    }


def test_vertical_analytic_case() -> None:
    times = quadratic_front_times_ns(
        [[0, 0, 0], [3, 4, 0], [0, 0, 6]], [0, 0, -1], [0, 0, 0], 100.0, 2.0
    )
    assert_allclose(times, [100.0, 150.0, 100.0 - 6.0 / C_M_PER_NS], atol=1e-12, rtol=0)
    assert times.dtype == np.float64
    assert times.shape == (3,)


def test_tilted_independent_scalar_formula(inputs: dict) -> None:
    expected = []
    for position in inputs["station_positions_m"]:
        dx, dy, dz = position - inputs["core_position_m"]
        ux, uy, uz = inputs["propagation_direction"]
        longitudinal = dx * ux + dy * uy + dz * uz
        # An independent algebraic expression is safe at these ordinary scales.
        rho_squared = dx**2 + dy**2 + dz**2 - longitudinal**2
        expected.append(10_000.0 + longitudinal / C_M_PER_NS + 1.0e-4 * rho_squared)
    assert_allclose(quadratic_front_times_ns(**inputs), expected, rtol=1e-14, atol=1e-11)


def test_zero_curvature_matches_plane_model(inputs: dict) -> None:
    inputs["curvature_ns_per_m2"] = 0.0
    expected = predict_station_times_ns(
        inputs["core_time_ns"],
        inputs["propagation_direction"],
        inputs["station_positions_m"],
        inputs["core_position_m"],
    )
    assert_array_equal(quadratic_front_times_ns(**inputs), expected)


def test_core_and_axis_points_have_no_curvature_delay(inputs: dict) -> None:
    distances = np.array([-1000.0, 0.0, 1000.0])
    inputs["station_positions_m"] = (
        inputs["core_position_m"] + distances[:, None] * inputs["propagation_direction"]
    )
    expected = inputs["core_time_ns"] + distances / C_M_PER_NS
    assert_allclose(quadratic_front_times_ns(**inputs), expected, atol=1e-11, rtol=1e-14)


def test_curvature_increment_is_nonnegative_and_linear(inputs: dict) -> None:
    baseline = quadratic_front_times_ns(**(inputs | {"curvature_ns_per_m2": 0.0}))
    first = quadratic_front_times_ns(**inputs) - baseline
    second = quadratic_front_times_ns(**(inputs | {"curvature_ns_per_m2": 2e-4})) - baseline
    assert np.all(first >= 0.0)
    assert_allclose(second, 2 * first, rtol=1e-12, atol=1e-11)


def test_translation_and_time_offset_invariance(inputs: dict) -> None:
    expected = quadratic_front_times_ns(**inputs)
    translation = np.array([30_000.0, -20_000.0, 4000.0])
    inputs["station_positions_m"] += translation
    inputs["core_position_m"] += translation
    inputs["core_time_ns"] += 4321.0
    assert_allclose(quadratic_front_times_ns(**inputs), expected + 4321, atol=1e-11, rtol=1e-14)


def test_rotation_about_vertical_preserves_times(inputs: dict) -> None:
    expected = quadratic_front_times_ns(**inputs)
    angle = 1.234
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]]
    )
    inputs["station_positions_m"] = inputs["station_positions_m"] @ rotation.T
    inputs["core_position_m"] = rotation @ inputs["core_position_m"]
    inputs["propagation_direction"] = rotation @ inputs["propagation_direction"]
    assert_allclose(quadratic_front_times_ns(**inputs), expected, atol=1e-11, rtol=1e-14)


def test_readonly_inputs_are_not_mutated(inputs: dict) -> None:
    originals = {}
    for key, value in inputs.items():
        if isinstance(value, np.ndarray):
            originals[key] = value.copy()
            value.flags.writeable = False
    first = quadratic_front_times_ns(**inputs)
    first[:] = -123.0
    second = quadratic_front_times_ns(**inputs)
    assert np.all(second != -123.0)
    for key, value in originals.items():
        assert_array_equal(inputs[key], value)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("station_positions_m", [], "shape"),
        ("station_positions_m", np.empty((0, 3)), "shape"),
        ("station_positions_m", [1, 2, 3], "shape"),
        ("station_positions_m", [[1, 2]], "shape"),
        ("station_positions_m", np.zeros((2, 1, 3)), "shape"),
        ("station_positions_m", [[np.nan, 0, 0]], "finite"),
        ("station_positions_m", [[np.inf, 0, 0]], "finite"),
        ("station_positions_m", [[1 + 2j, 0, 0]], "real numeric"),
        ("station_positions_m", [[True, False, True]], "real numeric"),
        ("station_positions_m", [["1", "2", "3"]], "real numeric"),
        ("propagation_direction", [[0, 0, -1]], "shape"),
        ("propagation_direction", [0, 0], "shape"),
        ("propagation_direction", [0, 0, 0], "unit length"),
        ("propagation_direction", [0, 0, -2], "unit length"),
        ("propagation_direction", [0, 0, -1.000001], "unit length"),
        ("propagation_direction", [0, 0, 1], "downward"),
        ("propagation_direction", [1, 0, 0], "downward"),
        ("propagation_direction", [0, np.nan, -1], "finite"),
        ("propagation_direction", [1.7e308, 0, -1.7e308], "unit length"),
        ("core_position_m", [[0, 0, 0]], "shape"),
        ("core_position_m", [0, 0], "shape"),
        ("core_position_m", [0, np.inf, 0], "finite"),
        ("core_time_ns", [10.0], "scalar"),
        ("core_time_ns", np.nan, "finite"),
        ("core_time_ns", True, "real numeric"),
        ("curvature_ns_per_m2", -1e-4, "nonnegative"),
        ("curvature_ns_per_m2", [1e-4], "scalar"),
        ("curvature_ns_per_m2", np.inf, "finite"),
        ("curvature_ns_per_m2", False, "real numeric"),
        ("curvature_ns_per_m2", 1j, "real numeric"),
    ],
)
def test_invalid_inputs_raise_value_error(inputs: dict, name: str, value, message: str) -> None:
    inputs[name] = value
    with pytest.raises(ValueError, match=message):
        quadratic_front_times_ns(**inputs)


def test_intermediate_overflow_is_explicit(inputs: dict) -> None:
    inputs["station_positions_m"] = [[1e308, 0, 0]]
    inputs["core_position_m"] = [-1e308, 0, 0]
    with pytest.raises(ValueError, match="finite float64"):
        quadratic_front_times_ns(**inputs)


def test_curvature_overflow_is_explicit(inputs: dict) -> None:
    inputs["station_positions_m"] = [[1e200, 0, 0]]
    with pytest.raises(ValueError, match="finite float64"):
        quadratic_front_times_ns(**inputs)


def test_zero_curvature_does_not_need_transverse_square() -> None:
    result = quadratic_front_times_ns([[1e200, 0, 0]], [0, 0, -1], [0, 0, 0], 123.0, 0)
    assert_array_equal(result, [123.0])


def test_final_time_overflow_is_explicit() -> None:
    with pytest.raises(ValueError, match="finite float64"):
        quadratic_front_times_ns([[0, 0, -1e307]], [0, 0, -1], [0, 0, 0], 1.7e308, 0)


def test_multiplication_overflow_is_explicit() -> None:
    with pytest.raises(ValueError, match="finite float64"):
        quadratic_front_times_ns([[1e100, 0, 0]], [0, 0, -1], [0, 0, 0], 0, 1e200)
