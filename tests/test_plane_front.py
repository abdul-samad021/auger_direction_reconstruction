"""Scientific and numerical contract tests for plane-front reconstruction."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from numpy.typing import NDArray

import auger_reco.physics.plane_front as plane_front

type FloatArray = NDArray[np.float64]

TRUE_ZENITH_DEG = 42.0
TRUE_AZIMUTH_DEG = 55.0
TRUE_ORIGIN_TIME_NS = 100_000.0

# An independent reference value prevents a wrong production constant from
# silently being reused while generating the expected synthetic answers.
REFERENCE_C_M_PER_NS = 0.299792458

# These are much tighter than detector-level accuracy while still allowing
# tiny platform-dependent floating-point differences.
EXACT_ANGLE_TOLERANCE_DEG = 1.0e-6
EXACT_TIME_TOLERANCE_NS = 1.0e-6


@pytest.fixture
def station_positions_m() -> FloatArray:
    """Return a reusable, non-degenerate 13-station detector layout."""

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
def timing_uncertainties_ns() -> FloatArray:
    """Return heterogeneous timing uncertainties for the 13 stations."""

    return np.array(
        [
            8.0,
            12.0,
            10.0,
            15.0,
            7.0,
            18.0,
            11.0,
            9.0,
            14.0,
            8.0,
            16.0,
            10.0,
            13.0,
        ],
        dtype=np.float64,
    )


def _make_exact_event(
    positions_m: FloatArray,
    *,
    zenith_deg: float = TRUE_ZENITH_DEG,
    azimuth_deg: float = TRUE_AZIMUTH_DEG,
    origin_time_ns: float = TRUE_ORIGIN_TIME_NS,
) -> tuple[FloatArray, FloatArray]:
    """Generate a known sky direction and exact plane-front station times."""

    zenith_rad = np.deg2rad(zenith_deg)
    azimuth_rad = np.deg2rad(azimuth_deg)

    # Independently implement:
    #
    # a = (sin(theta)cos(phi), sin(theta)sin(phi), cos(theta))
    #
    # where a points upward toward the cosmic ray's sky-arrival direction.
    sky_direction = np.array(
        [
            np.sin(zenith_rad) * np.cos(azimuth_rad),
            np.sin(zenith_rad) * np.sin(azimuth_rad),
            np.cos(zenith_rad),
        ],
        dtype=np.float64,
    )

    # The shower propagates in the direction opposite the sky-arrival vector.
    propagation_direction = -sky_direction

    # Generate exact station times from:
    #
    # t_i = t_0 + r_i dot u / c
    exact_times_ns = origin_time_ns + positions_m @ propagation_direction / REFERENCE_C_M_PER_NS

    return sky_direction, exact_times_ns


@pytest.mark.parametrize(
    ("zenith_deg", "azimuth_deg", "expected_direction"),
    [
        (0.0, 137.0, np.array([0.0, 0.0, 1.0])),
        (90.0, 0.0, np.array([1.0, 0.0, 0.0])),
        (90.0, 90.0, np.array([0.0, 1.0, 0.0])),
    ],
)
def test_sky_angle_conversion_matches_cardinal_directions(
    zenith_deg: float,
    azimuth_deg: float,
    expected_direction: FloatArray,
) -> None:
    """Angle conversion must agree with independently specified axes."""

    actual_direction = plane_front.sky_direction_from_angles(
        np.deg2rad(zenith_deg),
        np.deg2rad(azimuth_deg),
    )

    np.testing.assert_allclose(
        actual_direction,
        expected_direction,
        rtol=0.0,
        atol=1.0e-15,
    )

    assert plane_front.C_M_PER_NS == REFERENCE_C_M_PER_NS


def test_predict_station_times_uses_the_expected_sign_convention() -> None:
    """A station farther along propagation must be reached later."""

    # c metres is exactly one light-nanosecond.
    positions_m = np.array(
        [
            [0.0, 0.0, 0.0],
            [plane_front.C_M_PER_NS, 0.0, 0.0],
            [0.0, plane_front.C_M_PER_NS, 0.0],
        ],
        dtype=np.float64,
    )

    predicted_times_ns = plane_front.predict_station_times_ns(
        reference_time_ns=100.0,
        propagation_direction=np.array([1.0, 0.0, 0.0]),
        station_positions_m=positions_m,
        reference_position_m=np.zeros(3),
    )

    # Moving one light-nanosecond in +x delays only the second station by 1 ns.
    np.testing.assert_allclose(
        predicted_times_ns,
        np.array([100.0, 101.0, 100.0]),
        rtol=0.0,
        atol=1.0e-12,
    )


def test_exact_nonplanar_event_is_recovered(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """The complete fitter must recover noiseless synthetic truth."""

    true_sky_direction, exact_times_ns = _make_exact_event(station_positions_m)

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
        weighting="timing",
    )

    angular_error_deg = plane_front.angular_separation_deg(
        result.sky_direction,
        true_sky_direction,
    )

    assert angular_error_deg < EXACT_ANGLE_TOLERANCE_DEG

    assert result.zenith_deg == pytest.approx(
        TRUE_ZENITH_DEG,
        abs=EXACT_ANGLE_TOLERANCE_DEG,
    )

    assert result.azimuth_deg == pytest.approx(
        TRUE_AZIMUTH_DEG,
        abs=EXACT_ANGLE_TOLERANCE_DEG,
    )

    assert result.origin_time_ns == pytest.approx(
        TRUE_ORIGIN_TIME_NS,
        abs=EXACT_TIME_TOLERANCE_NS,
    )

    np.testing.assert_allclose(
        result.predicted_times_ns,
        exact_times_ns,
        rtol=0.0,
        atol=EXACT_TIME_TOLERANCE_NS,
    )

    assert result.maximum_absolute_residual_ns < EXACT_TIME_TOLERANCE_NS

    # This particular station layout genuinely spans x, y, and z.
    assert result.full_geometry_rank == 3

    # The final nonlinear problem has three locally identifiable parameters:
    # reference time and two direction slopes.
    assert result.final_jacobian_rank == 3

    assert result.degrees_of_freedom == len(station_positions_m) - 3

    np.testing.assert_allclose(
        result.propagation_direction,
        -result.sky_direction,
        rtol=0.0,
        atol=1.0e-15,
    )

    # Verify that top-level optimizer metadata agrees with the selected
    # per-initializer diagnostic record.
    selected_attempt = next(
        attempt
        for attempt in result.optimizer_attempts
        if attempt.initializer == result.initializer_used
    )

    assert selected_attempt.accepted is True

    assert selected_attempt.final_parameters == result.optimizer_parameters

    assert selected_attempt.objective_sum_squares == pytest.approx(result.objective_sum_squares)

    assert result.optimizer_function_evaluations >= 1
    assert np.isfinite(result.optimizer_cost)
    assert np.isfinite(result.optimizer_optimality)


@pytest.mark.parametrize(
    ("zenith_deg", "azimuth_deg"),
    [
        (20.0, 5.0),
        (35.0, 95.0),
        (50.0, 185.0),
        (60.0, 275.0),
        (35.0, 359.0),
    ],
)
def test_rank_two_flat_array_recovers_every_azimuth_quadrant(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
    zenith_deg: float,
    azimuth_deg: float,
) -> None:
    """A flat array must recover directions in every azimuth quadrant."""

    flat_positions_m = station_positions_m.copy()

    # Every station now has identical elevation. After centring, all delta-z
    # values become zero, so the linear coordinate geometry has rank two.
    flat_positions_m[:, 2] = 1400.0

    true_sky_direction, exact_times_ns = _make_exact_event(
        flat_positions_m,
        zenith_deg=zenith_deg,
        azimuth_deg=azimuth_deg,
    )

    result = plane_front.fit_plane_front(
        flat_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
    )

    assert (
        plane_front.angular_separation_deg(
            result.sky_direction,
            true_sky_direction,
        )
        < EXACT_ANGLE_TOLERANCE_DEG
    )

    # Coordinate geometry is rank two, but the physical unit-vector condition
    # and downward branch allow the complete direction to be reconstructed.
    assert result.full_geometry_rank == 2
    assert result.final_jacobian_rank == 3
    assert result.degrees_of_freedom == len(flat_positions_m) - 3
    assert np.isinf(result.full_condition_number)

    assert "rank_two_surface_geometry" in result.quality_flags


def test_vertical_event_marks_azimuth_as_undefined(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Azimuth has no physical meaning when zenith is zero."""

    true_sky_direction, exact_times_ns = _make_exact_event(
        station_positions_m,
        zenith_deg=0.0,
        azimuth_deg=247.0,
    )

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
    )

    assert (
        plane_front.angular_separation_deg(
            result.sky_direction,
            true_sky_direction,
        )
        < EXACT_ANGLE_TOLERANCE_DEG
    )

    assert result.zenith_deg == pytest.approx(
        0.0,
        abs=EXACT_ANGLE_TOLERANCE_DEG,
    )

    # All azimuths describe the same point when the direction is straight up.
    assert np.isnan(result.azimuth_deg)

    assert "azimuth_undefined_near_vertical" in result.quality_flags


def test_noisy_fits_reconstruct_and_report_distinct_objectives(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """A deterministic noisy case must report each minimized objective."""

    true_sky_direction, exact_times_ns = _make_exact_event(station_positions_m)

    # A fixed seed makes the test repeatable on every run.
    random_generator = np.random.default_rng(2026)

    noisy_times_ns = exact_times_ns + random_generator.normal(
        loc=0.0,
        scale=timing_uncertainties_ns,
    )

    weighted_result = plane_front.fit_plane_front(
        station_positions_m,
        noisy_times_ns,
        timing_uncertainties_ns,
        weighting="timing",
    )

    uniform_result = plane_front.fit_plane_front(
        station_positions_m,
        noisy_times_ns,
        timing_uncertainties_ns,
        weighting="uniform",
    )

    # These are broad smoke-test limits, not claimed detector performance.
    assert (
        plane_front.angular_separation_deg(
            weighted_result.sky_direction,
            true_sky_direction,
        )
        < 0.5
    )

    assert (
        plane_front.angular_separation_deg(
            uniform_result.sky_direction,
            true_sky_direction,
        )
        < 0.5
    )

    # For timing weighting, the minimized residuals are e_i / dt_i.
    # Therefore, objective sum of squares equals chi-square.
    assert weighted_result.objective_sum_squares == pytest.approx(weighted_result.chi_square)

    # For uniform weighting, the fit scale is one for every station.
    # Therefore, the numerical objective equals raw timing RSS.
    assert uniform_result.objective_sum_squares == pytest.approx(
        uniform_result.residual_sum_squares_ns2
    )

    comparison_tolerance = 1.0e-10

    # WLS directly minimizes chi-square, so its chi-square cannot be worse
    # than the chi-square obtained from the OLS solution, apart from rounding.
    assert weighted_result.chi_square <= (uniform_result.chi_square * (1.0 + comparison_tolerance))

    # OLS directly minimizes raw RSS, so its RSS cannot be worse than the
    # raw RSS obtained from the WLS solution, apart from rounding.
    assert uniform_result.residual_sum_squares_ns2 <= (
        weighted_result.residual_sum_squares_ns2 * (1.0 + comparison_tolerance)
    )

    np.testing.assert_allclose(
        weighted_result.objective_residuals,
        weighted_result.standardized_residuals,
        rtol=0.0,
        atol=1.0e-12,
    )

    np.testing.assert_allclose(
        uniform_result.objective_residuals,
        uniform_result.residuals_ns,
        rtol=0.0,
        atol=1.0e-12,
    )

    # Independently recompute the diagnostic quantities from the public result.
    expected_weighted_residuals_ns = noisy_times_ns - weighted_result.predicted_times_ns

    expected_weighted_standardized = expected_weighted_residuals_ns / timing_uncertainties_ns

    np.testing.assert_allclose(
        weighted_result.residuals_ns,
        expected_weighted_residuals_ns,
        rtol=0.0,
        atol=1.0e-12,
    )

    np.testing.assert_allclose(
        weighted_result.standardized_residuals,
        expected_weighted_standardized,
        rtol=0.0,
        atol=1.0e-12,
    )

    assert weighted_result.chi_square == pytest.approx(
        float(np.sum(expected_weighted_standardized**2))
    )

    assert weighted_result.rms_residual_ns == pytest.approx(
        float(np.sqrt(np.mean(expected_weighted_residuals_ns**2)))
    )

    assert weighted_result.maximum_absolute_residual_ns == pytest.approx(
        float(np.max(np.abs(expected_weighted_residuals_ns)))
    )

    assert np.isfinite(weighted_result.reduced_chi_square)
    assert np.isfinite(uniform_result.reduced_chi_square)


def test_repeated_fit_is_deterministic(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Identical inputs and options must produce the same reconstruction."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    noisy_times_ns = exact_times_ns + np.random.default_rng(7391).normal(
        loc=0.0,
        scale=timing_uncertainties_ns,
    )

    first = plane_front.fit_plane_front(
        station_positions_m,
        noisy_times_ns,
        timing_uncertainties_ns,
    )

    second = plane_front.fit_plane_front(
        station_positions_m,
        noisy_times_ns,
        timing_uncertainties_ns,
    )

    np.testing.assert_allclose(
        first.sky_direction,
        second.sky_direction,
        rtol=0.0,
        atol=1.0e-12,
    )

    assert first.objective_sum_squares == pytest.approx(
        second.objective_sum_squares,
        rel=0.0,
        abs=1.0e-12,
    )


def test_result_arrays_and_dataclass_are_immutable(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Callers must not be able to corrupt a completed result."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
    )

    # The dataclass itself is frozen.
    with pytest.raises(FrozenInstanceError):
        result.zenith_deg = 0.0  # type: ignore[misc]

    returned_arrays = (
        result.sky_direction,
        result.propagation_direction,
        result.reference_position_m,
        result.predicted_times_ns,
        result.residuals_ns,
        result.objective_residuals,
        result.standardized_residuals,
        result.singular_values,
    )

    assert all(values.dtype == np.float64 for values in returned_arrays)

    assert all(not values.flags.writeable for values in returned_arrays)

    # The arrays inside the result are also read-only.
    with pytest.raises(ValueError):
        result.sky_direction[0] = 0.0


def test_collinear_station_geometry_is_rejected() -> None:
    """Stations on one line cannot determine a two-dimensional tilt."""

    collinear_positions_m = np.array(
        [
            [0.0, 0.0, 0.0],
            [1000.0, 0.0, 0.0],
            [2000.0, 0.0, 0.0],
            [3000.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )

    with pytest.raises(
        plane_front.DegenerateStationGeometryError,
        match="at least two independent spatial directions",
    ):
        plane_front.fit_plane_front(
            collinear_positions_m,
            observed_times_ns=np.zeros(4),
            timing_uncertainties_ns=np.ones(4),
        )


@pytest.mark.parametrize(
    "invalid_uncertainty",
    [
        0.0,
        -1.0,
        np.nan,
        np.inf,
    ],
)
def test_nonpositive_or_nonfinite_uncertainty_is_rejected(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
    invalid_uncertainty: float,
) -> None:
    """Timing weights require finite, positive uncertainties."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    invalid_uncertainties_ns = timing_uncertainties_ns.copy()

    invalid_uncertainties_ns[0] = invalid_uncertainty

    with pytest.raises(
        ValueError,
        match="Timing uncertainties",
    ):
        plane_front.fit_plane_front(
            station_positions_m,
            exact_times_ns,
            invalid_uncertainties_ns,
        )


def test_wrong_shapes_and_nonfinite_measurements_are_rejected(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Reject malformed arrays before optimization begins."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    with pytest.raises(
        ValueError,
        match=r"station_positions_m must have shape \(N, 3\)",
    ):
        plane_front.fit_plane_front(
            station_positions_m[:, :2],
            exact_times_ns,
            timing_uncertainties_ns,
        )

    with pytest.raises(
        ValueError,
        match=r"observed_times_ns must have shape \(N,\)",
    ):
        plane_front.fit_plane_front(
            station_positions_m,
            exact_times_ns[:-1],
            timing_uncertainties_ns,
        )

    with pytest.raises(
        ValueError,
        match=r"timing_uncertainties_ns must have shape \(N,\)",
    ):
        plane_front.fit_plane_front(
            station_positions_m,
            exact_times_ns,
            timing_uncertainties_ns[:-1],
        )

    nonfinite_times_ns = exact_times_ns.copy()
    nonfinite_times_ns[0] = np.inf

    with pytest.raises(
        ValueError,
        match="Observed times must be finite",
    ):
        plane_front.fit_plane_front(
            station_positions_m,
            nonfinite_times_ns,
            timing_uncertainties_ns,
        )

    nonfinite_positions_m = station_positions_m.copy()
    nonfinite_positions_m[0, 0] = np.nan

    with pytest.raises(
        ValueError,
        match="Station positions must be finite",
    ):
        plane_front.fit_plane_front(
            nonfinite_positions_m,
            exact_times_ns,
            timing_uncertainties_ns,
        )


def test_too_few_stations_are_rejected() -> None:
    """Three fitted parameters need four stations for residual checking."""

    with pytest.raises(
        ValueError,
        match="At least 4 stations are required",
    ):
        plane_front.fit_plane_front(
            station_positions_m=np.zeros((3, 3)),
            observed_times_ns=np.zeros(3),
            timing_uncertainties_ns=np.ones(3),
        )


def test_unknown_weighting_mode_is_rejected(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Runtime validation must protect dynamically typed callers."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    with pytest.raises(
        ValueError,
        match="weighting must be either",
    ):
        plane_front.fit_plane_front(
            station_positions_m,
            exact_times_ns,
            timing_uncertainties_ns,
            weighting="inverse_signal",  # type: ignore[arg-type]
        )


def test_invalid_fit_option_is_rejected() -> None:
    """Invalid settings must fail when configuration is constructed."""

    with pytest.raises(
        ValueError,
        match="minimum_stations must be at least four",
    ):
        plane_front.PlaneFrontFitOptions(minimum_stations=3)


def test_configured_condition_threshold_produces_quality_flag(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Scientific options must control geometry-quality reporting."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    # A threshold of one intentionally makes this valid geometry cross the
    # warning boundary, allowing the warning mechanism to be tested.
    options = plane_front.PlaneFrontFitOptions(
        surface_condition_warning_threshold=1.0,
    )

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
        options=options,
    )

    assert result.options == options

    assert result.surface_condition_number > options.surface_condition_warning_threshold

    assert "ill_conditioned_surface_geometry" in result.quality_flags


def test_near_horizon_fit_is_flagged(
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """A representable near-horizon arrival must expose its warning."""

    # Exactly 90 degrees cannot be represented by finite slopes. A direction
    # at 89.5 degrees remains representable but is intentionally flagged.
    true_sky_direction, exact_times_ns = _make_exact_event(
        station_positions_m,
        zenith_deg=89.5,
        azimuth_deg=70.0,
    )

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
    )

    assert "near_horizon_slope_parameterization" in result.quality_flags

    assert (
        plane_front.angular_separation_deg(
            result.sky_direction,
            true_sky_direction,
        )
        < 1.0e-5
    )


def test_one_failed_optimizer_start_does_not_abort_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """The multistart fitter must survive one numerical exception."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    # Save the real function so calls after the injected failure can proceed.
    original_fit_from_seed = plane_front._fit_from_seed
    number_of_calls = 0

    def fail_first_attempt(
        system,
        propagation_seed,
        options,
    ):
        nonlocal number_of_calls

        number_of_calls += 1

        if number_of_calls == 1:
            raise FloatingPointError("Injected single-start failure for testing.")

        return original_fit_from_seed(
            system,
            propagation_seed,
            options,
        )

    monkeypatch.setattr(
        plane_front,
        "_fit_from_seed",
        fail_first_attempt,
    )

    result = plane_front.fit_plane_front(
        station_positions_m,
        exact_times_ns,
        timing_uncertainties_ns,
    )

    failed_attempts = [attempt for attempt in result.optimizer_attempts if not attempt.accepted]

    assert number_of_calls >= 2

    assert any(attempt.exception_type == "FloatingPointError" for attempt in failed_attempts)

    assert any(attempt.accepted for attempt in result.optimizer_attempts)

    assert any(flag.startswith("failed_initializers:") for flag in result.quality_flags)


def test_all_failed_optimizer_starts_raise_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    station_positions_m: FloatArray,
    timing_uncertainties_ns: FloatArray,
) -> None:
    """Total failure must retain diagnostics for every attempted seed."""

    _, exact_times_ns = _make_exact_event(station_positions_m)

    def always_fail(*_args, **_kwargs):
        raise FloatingPointError("Injected total optimizer failure for testing.")

    monkeypatch.setattr(
        plane_front,
        "_fit_from_seed",
        always_fail,
    )

    with pytest.raises(plane_front.PlaneFrontOptimizationError) as error_info:
        plane_front.fit_plane_front(
            station_positions_m,
            exact_times_ns,
            timing_uncertainties_ns,
        )

    attempts = error_info.value.attempts

    assert attempts
    assert len(attempts) >= 2

    assert all(not attempt.accepted for attempt in attempts)

    assert all(attempt.scipy_success is False for attempt in attempts)

    assert all(attempt.status is None for attempt in attempts)

    assert all(attempt.exception_type == "FloatingPointError" for attempt in attempts)

    assert all(
        attempt.message == "Injected total optimizer failure for testing." for attempt in attempts
    )
