"""Independent physics and numerical contracts for the known-core quadratic fitter.

The expected times are generated here from a scalar expansion, not by calling
the production timing generator. These tests establish implementation validity;
they do not establish how well a quadratic front describes real showers.
"""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from auger_reco.physics import curved_front, plane_front

REFERENCE_C_M_PER_NS = 0.299792458


@pytest.fixture
def positions() -> np.ndarray:
    """Unequal radii break the time-offset/curvature degeneracy of a ring."""
    return np.array(
        [
            [-1500.0, -1500.0, 35.0],
            [0.0, -1500.0, 22.0],
            [1500.0, -1500.0, 45.0],
            [-1500.0, 0.0, 18.0],
            [0.0, 0.0, 30.0],
            [1500.0, 0.0, 12.0],
            [-1500.0, 1500.0, 55.0],
            [0.0, 1500.0, 42.0],
            [1500.0, 1500.0, 60.0],
            [-750.0, -750.0, 28.0],
            [750.0, -750.0, 20.0],
            [-750.0, 750.0, 46.0],
            [750.0, 750.0, 38.0],
        ],
        dtype=np.float64,
    )


@pytest.fixture
def uncertainties() -> np.ndarray:
    return np.array([8, 12, 10, 15, 7, 18, 11, 9, 14, 8, 16, 10, 13], dtype=float)


def independent_event(
    positions: np.ndarray,
    *,
    core: np.ndarray | None = None,
    zenith_deg: float = 42.0,
    azimuth_deg: float = 55.0,
    core_time_ns: float = 100_000.0,
    curvature_ns_per_m2: float = 1.0e-4,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute dot and transverse-square terms independently of fitter code."""
    core = np.zeros(3) if core is None else core
    theta, phi = np.deg2rad([zenith_deg, azimuth_deg])
    sky = np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])
    ux, uy, uz = -sky
    expected = []
    for position in positions:
        dx, dy, dz = position - core
        projection = ux * dx + uy * dy + uz * dz
        transverse_squared = dx**2 + dy**2 + dz**2 - projection**2
        expected.append(
            core_time_ns
            + projection / REFERENCE_C_M_PER_NS
            + curvature_ns_per_m2 * transverse_squared
        )
    return sky, np.array(expected)


@pytest.mark.parametrize("azimuth_deg", [20.0, 110.0, 200.0, 290.0])
@pytest.mark.parametrize("flat", [False, True])
def test_exact_curved_recovery_across_quadrants(
    positions: np.ndarray, uncertainties: np.ndarray, azimuth_deg: float, flat: bool
) -> None:
    if flat:
        positions[:, 2] = 0.0
    core = np.array([210.0, -340.0, 0.0])
    truth, times = independent_event(positions, core=core, azimuth_deg=azimuth_deg)
    result = curved_front.fit_quadratic_front(positions, times, uncertainties, core_position_m=core)
    assert plane_front.angular_separation_deg(result.sky_direction, truth) < 1e-6
    assert result.curvature_ns_per_m2 == pytest.approx(1.0e-4, abs=1e-11)
    assert result.delay_at_1km_ns == pytest.approx(100.0, abs=1e-5)
    assert result.core_time_ns == pytest.approx(100_000.0, abs=1e-5)
    assert result.final_jacobian_rank == 4
    assert result.degrees_of_freedom == len(times) - 4
    assert_allclose(result.predicted_times_ns, times, rtol=0.0, atol=1e-5)
    assert_allclose(result.propagation_direction, -result.sky_direction, rtol=0.0, atol=1e-15)
    assert_allclose(result.core_position_m, core, rtol=0.0, atol=0.0)


@pytest.mark.parametrize("zenith_deg", [0.0, 1e-6, 60.0])
def test_vertical_near_vertical_and_inclined_recovery(
    positions: np.ndarray, uncertainties: np.ndarray, zenith_deg: float
) -> None:
    truth, times = independent_event(positions, zenith_deg=zenith_deg)
    result = curved_front.fit_quadratic_front(
        positions, times, uncertainties, core_position_m=np.zeros(3)
    )
    # Azimuth itself is undefined at the zenith; compare unit vectors instead.
    assert plane_front.angular_separation_deg(result.sky_direction, truth) < 1e-6
    assert result.delay_at_1km_ns == pytest.approx(100.0, abs=1e-5)
    assert_allclose(result.predicted_times_ns, times, rtol=0.0, atol=1e-5)


def test_zero_curvature_plane_limit_is_flagged_as_boundary(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    truth, times = independent_event(positions, curvature_ns_per_m2=0.0)
    result = curved_front.fit_quadratic_front(
        positions, times, uncertainties, core_position_m=np.zeros(3)
    )
    assert plane_front.angular_separation_deg(result.sky_direction, truth) < 1e-6
    assert 0.0 <= result.delay_at_1km_ns < 1e-5
    assert_allclose(result.predicted_times_ns, times, rtol=0.0, atol=1e-5)
    assert "curvature_at_lower_bound" in result.quality_flags
    assert "reduced_chi_square_nominal_boundary" in result.quality_flags


def test_translation_and_time_shift_invariance(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    core = np.array([350.0, -500.0, 40.0])
    _, times = independent_event(positions, core=core)
    first = curved_front.fit_quadratic_front(positions, times, uncertainties, core_position_m=core)
    translation = np.array([500_000.0, -300_000.0, 1400.0])
    shift_ns = 765_432.0
    moved = curved_front.fit_quadratic_front(
        positions + translation,
        times + shift_ns,
        uncertainties,
        core_position_m=core + translation,
    )
    assert plane_front.angular_separation_deg(first.sky_direction, moved.sky_direction) < 1e-6
    assert moved.core_time_ns - first.core_time_ns == pytest.approx(shift_ns, abs=1e-5)
    assert moved.curvature_ns_per_m2 == pytest.approx(first.curvature_ns_per_m2, abs=1e-11)
    assert_allclose(moved.predicted_times_ns, first.predicted_times_ns + shift_ns, atol=1e-5)


def test_rotation_about_vertical_preserves_fitted_direction_and_curvature(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    core = np.array([200.0, -100.0, 30.0])
    truth, times = independent_event(positions, core=core)
    angle = 1.23
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]]
    )
    result = curved_front.fit_quadratic_front(
        positions @ rotation.T, times, uncertainties, core_position_m=rotation @ core
    )
    assert plane_front.angular_separation_deg(result.sky_direction, rotation @ truth) < 1e-6
    assert result.delay_at_1km_ns == pytest.approx(100.0, abs=1e-5)


def test_noisy_objectives_and_nested_plane_comparison(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    core = np.array([320.0, -250.0, 0.0])
    _, exact = independent_event(positions, core=core)
    observed = exact + np.random.default_rng(77123).normal(0, uncertainties)
    fits = {}
    for weighting in ("timing", "uniform"):
        fit = curved_front.fit_quadratic_front(
            positions, observed, uncertainties, core_position_m=core, weighting=weighting
        )
        plane = plane_front.fit_plane_front(positions, observed, uncertainties, weighting=weighting)
        fits[weighting] = fit
        assert_allclose(fit.residuals_ns, observed - fit.predicted_times_ns, atol=1e-10)
        assert_allclose(fit.standardized_residuals, fit.residuals_ns / uncertainties, atol=1e-12)
        assert fit.chi_square == pytest.approx(float(np.sum(fit.standardized_residuals**2)))
        assert fit.reduced_chi_square == pytest.approx(fit.chi_square / (len(observed) - 4))
        assert fit.residual_sum_squares_ns2 == pytest.approx(float(np.sum(fit.residuals_ns**2)))
        objective = fit.chi_square if weighting == "timing" else fit.residual_sum_squares_ns2
        assert fit.objective_sum_squares == pytest.approx(objective)
        assert fit.objective_sum_squares <= plane.objective_sum_squares + 1e-5
    # Each fit minimizes its own objective, not necessarily the other objective.
    assert fits["timing"].chi_square <= fits["uniform"].chi_square + 1e-6
    assert (
        fits["uniform"].residual_sum_squares_ns2 <= fits["timing"].residual_sum_squares_ns2 + 1e-4
    )


def test_equal_uncertainties_have_equivalent_minimizers(positions: np.ndarray) -> None:
    dt = np.full(len(positions), 10.0)
    _, times = independent_event(positions)
    observed = times + np.random.default_rng(101).normal(0, dt)
    weighted, uniform = [
        curved_front.fit_quadratic_front(
            positions, observed, dt, core_position_m=np.zeros(3), weighting=mode
        )
        for mode in ("timing", "uniform")
    ]
    assert plane_front.angular_separation_deg(weighted.sky_direction, uniform.sky_direction) < 1e-5
    assert_allclose(weighted.predicted_times_ns, uniform.predicted_times_ns, rtol=0.0, atol=1e-3)
    assert weighted.chi_square == pytest.approx(uniform.chi_square, rel=1e-7)


def test_negative_curvature_data_cannot_escape_nonnegative_fit_constraint(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    """An intentionally nonphysical input must not defeat the declared bound."""
    _, times = independent_event(positions, curvature_ns_per_m2=-1.0e-4)
    result = curved_front.fit_quadratic_front(
        positions, times, uncertainties, core_position_m=np.zeros(3)
    )
    assert result.curvature_ns_per_m2 >= 0.0
    assert result.delay_at_1km_ns >= 0.0
    assert result.chi_square > 1.0
    assert np.all(np.isfinite(result.predicted_times_ns))


def test_row_permutation_does_not_change_the_reconstruction(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    _, times = independent_event(positions)
    observed = times + np.random.default_rng(902).normal(0, uncertainties)
    permutation = np.random.default_rng(19).permutation(len(times))
    first = curved_front.fit_quadratic_front(
        positions, observed, uncertainties, core_position_m=np.zeros(3)
    )
    second = curved_front.fit_quadratic_front(
        positions[permutation],
        observed[permutation],
        uncertainties[permutation],
        core_position_m=np.zeros(3),
    )
    assert plane_front.angular_separation_deg(first.sky_direction, second.sky_direction) < 1e-5
    assert_allclose(
        second.predicted_times_ns, first.predicted_times_ns[permutation], atol=1e-3, rtol=0
    )
    assert second.delay_at_1km_ns == pytest.approx(first.delay_at_1km_ns, abs=1e-4)


def test_readonly_inputs_and_returned_arrays_do_not_alias_inputs(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    core = np.zeros(3)
    _, times = independent_event(positions)
    arrays = (positions, times, uncertainties, core)
    originals = tuple(array.copy() for array in arrays)
    for array in arrays:
        array.flags.writeable = False
    result = curved_front.fit_quadratic_front(positions, times, uncertainties, core_position_m=core)
    for array, original in zip(arrays, originals, strict=True):
        assert_array_equal(array, original)
        assert not np.shares_memory(result.predicted_times_ns, array)
        assert not np.shares_memory(result.core_position_m, array)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("station_positions_m", np.zeros((13, 2))),
        ("station_positions_m", np.zeros((13, 1, 3))),
        ("station_positions_m", np.full((13, 3), np.nan)),
        ("station_positions_m", np.full((13, 3), np.inf)),
        ("observed_times_ns", np.zeros((13, 1))),
        ("observed_times_ns", np.zeros(12)),
        ("observed_times_ns", np.full(13, np.nan)),
        ("timing_uncertainties_ns", np.zeros(13)),
        ("timing_uncertainties_ns", np.full(13, -1.0)),
        ("timing_uncertainties_ns", np.full(13, np.inf)),
        ("timing_uncertainties_ns", np.full(13, np.nan)),
        ("timing_uncertainties_ns", np.ones((13, 1))),
        ("core_position_m", np.zeros(2)),
        ("core_position_m", np.zeros((1, 3))),
        ("core_position_m", [0, 0, np.inf]),
        ("core_position_m", [0, 0, np.nan]),
        ("weighting", "signal"),
    ],
)
def test_invalid_measurements_raise_explicit_error(
    positions: np.ndarray, uncertainties: np.ndarray, field: str, bad_value: object
) -> None:
    _, times = independent_event(positions)
    kwargs = {
        "station_positions_m": positions,
        "observed_times_ns": times,
        "timing_uncertainties_ns": uncertainties,
        "core_position_m": np.zeros(3),
        "weighting": "timing",
    }
    kwargs[field] = bad_value
    with pytest.raises(ValueError):
        curved_front.fit_quadratic_front(**kwargs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_stations": 4},
        {"maximum_function_evaluations": 0},
        {"optimizer_ftol": 0.0},
        {"optimizer_xtol": np.nan},
        {"optimizer_gtol": -1.0},
        {"positive_curvature_seeds_ns": (-1.0,)},
        {"positive_curvature_seeds_ns": (np.inf,)},
        {"boundary_curvature_tolerance_ns": -1.0},
    ],
)
def test_invalid_options_raise_explicit_error(overrides: dict) -> None:
    with pytest.raises(ValueError):
        curved_front.QuadraticFrontFitOptions(**overrides)


def test_uniform_fit_cannot_report_nonfinite_physical_chi_square(positions: np.ndarray) -> None:
    """Finite inputs can still overflow diagnostic arithmetic; reject explicitly."""
    _, exact = independent_event(positions)
    observed = exact + np.random.default_rng(593).normal(0, 10.0, len(positions))
    with pytest.raises(
        (ValueError, FloatingPointError, curved_front.QuadraticFrontOptimizationError)
    ):
        curved_front.fit_quadratic_front(
            positions,
            observed,
            np.full(len(positions), 1.0e-200),
            core_position_m=np.zeros(3),
            weighting="uniform",
        )


def test_options_are_immutable() -> None:
    options = curved_front.QuadraticFrontFitOptions()
    with pytest.raises(FrozenInstanceError):
        options.minimum_stations = 12


def test_too_few_stations_are_rejected(positions: np.ndarray, uncertainties: np.ndarray) -> None:
    _, times = independent_event(positions)
    with pytest.raises(ValueError):
        curved_front.fit_quadratic_front(
            positions[:4], times[:4], uncertainties[:4], core_position_m=np.zeros(3)
        )


def test_five_station_minimum_is_explicitly_configurable(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    indices = [0, 2, 4, 6, 8]
    selected = positions[indices]
    truth, times = independent_event(selected)
    result = curved_front.fit_quadratic_front(
        selected,
        times,
        uncertainties[indices],
        core_position_m=np.zeros(3),
        options=curved_front.QuadraticFrontFitOptions(minimum_stations=5),
    )
    assert result.number_of_stations == 5
    assert result.degrees_of_freedom == 1
    assert result.final_jacobian_rank == 4
    assert plane_front.angular_separation_deg(result.sky_direction, truth) < 1e-6


def test_collinear_geometry_is_rejected() -> None:
    positions = np.column_stack((np.linspace(-1000, 1000, 10), np.zeros((10, 2))))
    _, times = independent_event(positions)
    with pytest.raises(
        (curved_front.QuadraticFrontGeometryError, plane_front.DegenerateStationGeometryError)
    ):
        curved_front.fit_quadratic_front(
            positions, times, np.full(10, 10.0), core_position_m=np.zeros(3)
        )


def test_vertical_equal_radius_ring_cannot_identify_curvature_separately_from_time() -> None:
    angle = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    positions = np.column_stack((1000 * np.cos(angle), 1000 * np.sin(angle), np.zeros(12)))
    _, times = independent_event(positions, zenith_deg=0.0)
    with pytest.raises(curved_front.QuadraticFrontGeometryError) as error:
        curved_front.fit_quadratic_front(
            positions, times, np.full(12, 10.0), core_position_m=np.zeros(3)
        )
    assert error.value.attempts


def test_optimizer_exception_in_one_start_preserves_later_attempts(
    monkeypatch: pytest.MonkeyPatch, positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    _, times = independent_event(positions)
    original = curved_front._fit_from_seed
    calls = 0

    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise FloatingPointError("Injected first-start failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(curved_front, "_fit_from_seed", fail_first)
    result = curved_front.fit_quadratic_front(
        positions, times, uncertainties, core_position_m=np.zeros(3)
    )
    assert calls >= 2
    assert any(
        attempt.exception_type == "FloatingPointError" for attempt in result.optimizer_attempts
    )
    assert any(attempt.accepted for attempt in result.optimizer_attempts)
    assert_allclose(result.predicted_times_ns, times, rtol=0, atol=1e-5)


def test_all_failed_starts_return_structured_diagnostics(
    monkeypatch: pytest.MonkeyPatch, positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    _, times = independent_event(positions)

    def fail(*_args, **_kwargs):
        raise FloatingPointError("Injected all-start failure")

    monkeypatch.setattr(curved_front, "_fit_from_seed", fail)
    with pytest.raises(curved_front.QuadraticFrontOptimizationError) as error:
        curved_front.fit_quadratic_front(
            positions, times, uncertainties, core_position_m=np.zeros(3)
        )
    assert len(error.value.attempts) >= 2
    for attempt in error.value.attempts:
        assert not attempt.accepted
        assert attempt.exception_type == "FloatingPointError"
        assert "Injected all-start failure" in attempt.message


def test_unsuccessful_solver_status_retains_numerical_metadata(
    monkeypatch: pytest.MonkeyPatch, positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    """An optimizer result marked unsuccessful is not a successful fit."""
    _, times = independent_event(positions)
    original = curved_front._fit_from_seed

    def mark_unsuccessful(*args, **kwargs):
        result = original(*args, **kwargs)
        result.success = False
        result.status = 0
        result.message = "Injected evaluation-limit result"
        return result

    monkeypatch.setattr(curved_front, "_fit_from_seed", mark_unsuccessful)
    with pytest.raises(curved_front.QuadraticFrontOptimizationError) as error:
        curved_front.fit_quadratic_front(
            positions, times, uncertainties, core_position_m=np.zeros(3)
        )
    assert error.value.attempts
    for attempt in error.value.attempts:
        assert not attempt.accepted
        assert not attempt.scipy_success
        assert attempt.status == 0
        assert attempt.message == "Injected evaluation-limit result"
        assert attempt.function_evaluations >= 1
        assert attempt.jacobian_evaluations >= 1
        assert attempt.scipy_cost is not None
        assert attempt.optimality is not None
        assert len(attempt.final_parameters) == 4
        assert len(attempt.active_mask) == 4
        assert attempt.exception_type is None


def test_selected_optimizer_metadata_matches_attempt(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    _, times = independent_event(positions)
    result = curved_front.fit_quadratic_front(
        positions, times, uncertainties, core_position_m=np.zeros(3)
    )
    attempt = next(a for a in result.optimizer_attempts if a.initializer == result.initializer_used)
    assert attempt.accepted
    assert attempt.status == result.optimizer_status
    assert attempt.message == result.optimizer_message
    assert attempt.function_evaluations == result.optimizer_function_evaluations
    assert attempt.jacobian_evaluations == result.optimizer_jacobian_evaluations
    assert attempt.scipy_cost == result.optimizer_cost
    assert attempt.optimality == result.optimizer_optimality
    assert_allclose(attempt.final_parameters, result.optimizer_parameters, atol=0, rtol=0)
    assert_allclose(attempt.active_mask, result.optimizer_active_mask, atol=0, rtol=0)
    assert result.optimizer_cost == pytest.approx(result.objective_sum_squares / 2)


def test_analytic_jacobian_matches_independent_finite_differences(
    positions: np.ndarray, uncertainties: np.ndarray
) -> None:
    core = np.array([140.0, -220.0, 5.0])
    _, times = independent_event(positions, core=core)
    system = curved_front._prepare_system(positions, times, uncertainties, core, "timing")
    parameters = np.array([10.0, 0.5, -0.3, 80.0])
    actual = curved_front._objective_jacobian(parameters, system)
    numerical = np.empty_like(actual)
    for column, step in enumerate([1e-3, 1e-5, 1e-5, 1e-3]):
        upper, lower = parameters.copy(), parameters.copy()
        upper[column] += step
        lower[column] -= step
        numerical[:, column] = (
            curved_front._objective_residuals(upper, system)
            - curved_front._objective_residuals(lower, system)
        ) / (2 * step)
    assert_allclose(actual, numerical, atol=2e-6, rtol=2e-6)
