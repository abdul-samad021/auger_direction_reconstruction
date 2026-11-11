"""Known-core quadratic-front fitting for controlled timing experiments.

The phenomenological plane-plus-quadratic form has the same structure as the
paraboloidal approximation in the Pierre Auger surface-detector reconstruction
paper (arXiv:2007.09035, Eq. 5.3), after converting to our propagation convention.
This is not the complete Auger reconstruction or a detector-response simulator.
The supplied core is fixed: a true synthetic core makes this a known-core test;
an official reconstructed core makes a real-data fit reference-assisted.

Exactly horizontal showers are excluded by the slope parameterization. Results
near the horizon, near a curvature boundary, or with poorly constrained geometry
need the explicit quality flags and simulation-based validation, not unqualified
Gaussian error bars or ordinary chi-square significance claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import OptimizeResult, least_squares

from auger_reco.physics.plane_front import (
    C_M_PER_NS,
    OptimizerAttempt,
    PlaneFrontFitOptions,
    WeightingMode,
    fit_plane_front,
)

type FloatArray = NDArray[np.float64]

REFERENCE_DISTANCE_M = 1_000.0
REFERENCE_DISTANCE_SQUARED_M2 = REFERENCE_DISTANCE_M**2
_NUMERICAL_ERRORS = (
    ValueError,
    RuntimeError,
    FloatingPointError,
    OverflowError,
    np.linalg.LinAlgError,
)


@dataclass(frozen=True, slots=True)
class QuadraticFrontFitOptions:
    """Recorded settings, including scales used to define numerical quality."""

    minimum_stations: int = 6
    maximum_function_evaluations: int = 2_000
    positive_curvature_seeds_ns: tuple[float, ...] = (100.0,)
    optimizer_ftol: float = 1.0e-10
    optimizer_xtol: float = 1.0e-10
    optimizer_gtol: float = 1.0e-10
    jacobian_rank_relative_tolerance: float = 1.0e-10
    geometry_condition_warning_threshold: float = 1.0e8
    boundary_curvature_tolerance_ns: float = 1.0e-6
    minimum_sky_z_for_slopes: float = 1.0e-12
    near_horizon_sky_z_threshold: float = 1.0e-2
    vertical_azimuth_tolerance: float = 1.0e-12
    nested_objective_relative_tolerance: float = 1.0e-7
    nested_objective_absolute_tolerance: float = 1.0e-8

    def __post_init__(self) -> None:
        for name, lower in (("minimum_stations", 5), ("maximum_function_evaluations", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < lower:
                raise ValueError(f"{name} must be an integer at least {lower}.")
        positive_names = (
            "optimizer_ftol",
            "optimizer_xtol",
            "optimizer_gtol",
            "jacobian_rank_relative_tolerance",
            "geometry_condition_warning_threshold",
            "boundary_curvature_tolerance_ns",
            "minimum_sky_z_for_slopes",
            "near_horizon_sky_z_threshold",
            "vertical_azimuth_tolerance",
            "nested_objective_relative_tolerance",
            "nested_objective_absolute_tolerance",
        )
        for name in positive_names:
            value = _finite_scalar(getattr(self, name), name)
            if value <= 0.0:
                raise ValueError(f"{name} must be strictly positive.")
        for name in ("optimizer_ftol", "optimizer_xtol", "optimizer_gtol"):
            if getattr(self, name) <= np.finfo(np.float64).eps:
                raise ValueError(f"{name} must exceed float64 machine epsilon.")
        if not 0.0 < self.jacobian_rank_relative_tolerance < 1.0:
            raise ValueError("jacobian_rank_relative_tolerance must be below one.")
        if self.geometry_condition_warning_threshold < 1.0:
            raise ValueError("geometry_condition_warning_threshold must be at least one.")
        if not self.minimum_sky_z_for_slopes < self.near_horizon_sky_z_threshold < 1.0:
            raise ValueError("Sky-z thresholds must be ordered strictly between zero and one.")
        if self.vertical_azimuth_tolerance >= 1.0:
            raise ValueError("vertical_azimuth_tolerance must be below one.")
        if not isinstance(self.positive_curvature_seeds_ns, tuple):
            raise ValueError("positive_curvature_seeds_ns must be a nonempty tuple.")
        if not self.positive_curvature_seeds_ns:
            raise ValueError("At least one positive curvature seed is required.")
        for value in self.positive_curvature_seeds_ns:
            if _finite_scalar(value, "positive_curvature_seeds_ns entry") <= 0.0:
                raise ValueError("Curvature seed delays must be strictly positive.")


class QuadraticFrontOptimizationError(RuntimeError):
    """No trustworthy optimizer solution; retain every starting-point outcome."""

    def __init__(self, message: str, attempts: tuple[OptimizerAttempt, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


class QuadraticFrontGeometryError(ValueError):
    """The position geometry or final timing Jacobian is not identifiable."""

    def __init__(self, message: str, attempts: tuple[OptimizerAttempt, ...] = ()) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True, slots=True)
class QuadraticFrontFitResult:
    """Known-core fit with immutable arrays and explicit boundary diagnostics.

    ``degrees_of_freedom=N-4`` and ``reduced_chi_square`` are nominal diagnostics.
    At zero curvature, the nonnegative constraint violates the usual interior
    parameter assumption; neither an exact chi-square law nor a simple nested
    one-degree-of-freedom significance test follows from these fields.

    ``final_jacobian_condition_number`` uses column-normalized, weighted residual
    derivatives to avoid making its interpretation depend directly on parameter
    units. It is a local identifiability diagnostic, not a calibrated uncertainty.
    ``optimizer_parameters`` stores centered core time, two sky slopes, and the
    curvature delay at 1 km. Add ``time_origin_ns`` to the first for core time.
    """

    weighting: WeightingMode
    options: QuadraticFrontFitOptions
    number_of_stations: int
    core_position_m: FloatArray
    core_time_ns: float
    time_origin_ns: float
    curvature_ns_per_m2: float
    delay_at_1km_ns: float
    sky_direction: FloatArray
    propagation_direction: FloatArray
    zenith_deg: float
    azimuth_deg: float
    predicted_times_ns: FloatArray
    residuals_ns: FloatArray
    objective_residuals: FloatArray
    standardized_residuals: FloatArray
    objective_sum_squares: float
    residual_sum_squares_ns2: float
    chi_square: float
    degrees_of_freedom: int
    reduced_chi_square: float
    rms_residual_ns: float
    maximum_absolute_residual_ns: float
    final_jacobian_rank: int
    final_jacobian_condition_number: float
    final_jacobian_singular_values: FloatArray
    initializer_used: str
    initialization_messages: tuple[str, ...]
    optimizer_attempts: tuple[OptimizerAttempt, ...]
    quality_flags: tuple[str, ...]
    optimizer_status: int
    optimizer_message: str
    optimizer_function_evaluations: int
    optimizer_jacobian_evaluations: int | None
    optimizer_cost: float
    optimizer_optimality: float
    optimizer_active_mask: tuple[int, ...]
    optimizer_parameters: tuple[float, float, float, float]
    plane_objective_sum_squares: float | None


@dataclass(frozen=True, slots=True)
class _PreparedSystem:
    offsets_m: FloatArray
    centered_times_ns: FloatArray
    fit_scales_ns: FloatArray
    time_origin_ns: float


def _finite_array(value: ArrayLike, name: str) -> FloatArray:
    """Copy finite real numeric data; do not silently coerce strings or complex."""
    try:
        original = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric values.") from error
    if original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numbers, not Boolean or complex data.")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.array(original, dtype=np.float64, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite float64 values.")
    return result


def _finite_scalar(value: float, name: str) -> float:
    result = _finite_array(value, name)
    if result.ndim != 0:
        raise ValueError(f"{name} must be a scalar.")
    return float(result)


def _readonly(values: ArrayLike) -> FloatArray:
    result = np.array(values, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _validate_inputs(
    positions: ArrayLike,
    times: ArrayLike,
    uncertainties: ArrayLike,
    core: ArrayLike,
    options: QuadraticFrontFitOptions,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    """Validate shape, finite arithmetic, and a two-dimensional station layout."""
    positions_array = _finite_array(positions, "station_positions_m")
    times_array = _finite_array(times, "observed_times_ns")
    sigma_array = _finite_array(uncertainties, "timing_uncertainties_ns")
    core_array = _finite_array(core, "core_position_m")
    if positions_array.ndim != 2 or positions_array.shape[1] != 3:
        raise ValueError("station_positions_m must have shape (N, 3).")
    count = positions_array.shape[0]
    if count < options.minimum_stations:
        raise ValueError(f"At least {options.minimum_stations} stations are required.")
    if times_array.shape != (count,) or sigma_array.shape != (count,):
        raise ValueError("Times and timing uncertainties must each have shape (N,).")
    if core_array.shape != (3,):
        raise ValueError("core_position_m must have shape (3,).")
    if np.any(sigma_array <= 0.0):
        raise ValueError("Timing uncertainties must be strictly positive.")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            offsets = positions_array - positions_array[0]
            centered = offsets - np.mean(offsets, axis=0)
            singular_values = np.linalg.svd(centered, compute_uv=False)
    except (FloatingPointError, np.linalg.LinAlgError) as error:
        raise ValueError("Station geometry exceeds finite numerical arithmetic.") from error
    if singular_values[0] == 0.0 or (
        singular_values[1] <= options.jacobian_rank_relative_tolerance * singular_values[0]
    ):
        raise QuadraticFrontGeometryError("Stations must span at least two spatial dimensions.")
    return positions_array, times_array, sigma_array, core_array


def _prepare_system(
    positions: FloatArray,
    times: FloatArray,
    uncertainties: FloatArray,
    core: FloatArray,
    weighting: WeightingMode,
) -> _PreparedSystem:
    """Subtract a common epoch before optimization to preserve timing precision."""
    if weighting not in ("timing", "uniform"):
        raise ValueError("weighting must be 'timing' or 'uniform'.")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            offsets = positions - core
            centered_times = times - times[0]
            scales = uncertainties if weighting == "timing" else np.ones_like(times)
            # Check representative intermediate products once, before any seeds.
            squared_offsets = np.sum(offsets * offsets, axis=1)
            check = centered_times / scales
    except FloatingPointError as error:
        raise ValueError("Centered timing arithmetic exceeds finite float64 range.") from error
    if not np.isfinite(squared_offsets).all() or not np.isfinite(check).all():
        raise ValueError("Centered timing arithmetic must remain finite.")
    return _PreparedSystem(
        _readonly(offsets), _readonly(centered_times), _readonly(scales), float(times[0])
    )


def _sky_and_derivatives(slope_x: float, slope_y: float) -> tuple[FloatArray, FloatArray]:
    """Normalize (sx, sy, 1); differentiate that normalization analytically."""
    if not np.isfinite([slope_x, slope_y]).all():
        raise ValueError("Sky slopes must be finite.")
    norm = float(np.hypot(np.hypot(slope_x, slope_y), 1.0))
    sky = np.array([slope_x / norm, slope_y / norm, 1.0 / norm])
    derivative = (np.eye(3)[:, :2] - sky[:, None] * sky[None, :2]) / norm
    return sky, derivative


def _model_and_jacobian(
    parameters: FloatArray, system: _PreparedSystem
) -> tuple[FloatArray, FloatArray]:
    r"""Evaluate centered predictions and derivatives of tc + d.u/c + k rho^2.

    For a unit propagation vector, d(rho^2)/dq = -2(d.u)(d.du/dq).
    The axis distances therefore change at every direction trial; no true or
    reference direction is used inside the fitting objective.
    """
    offset_time, slope_x, slope_y, delay_at_1km = parameters
    sky, sky_derivative = _sky_and_derivatives(slope_x, slope_y)
    propagation = -sky
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        longitudinal = system.offsets_m @ propagation
        transverse = system.offsets_m - longitudinal[:, None] * propagation
        radial_scaled = np.sum(transverse * transverse, axis=1) / REFERENCE_DISTANCE_SQUARED_M2
        curvature = delay_at_1km / REFERENCE_DISTANCE_SQUARED_M2
        predictions = offset_time + longitudinal / C_M_PER_NS + delay_at_1km * radial_scaled
        longitudinal_derivative = system.offsets_m @ (-sky_derivative)
        direction_derivative = (1.0 / C_M_PER_NS - 2.0 * curvature * longitudinal)[
            :, None
        ] * longitudinal_derivative
        jacobian = np.column_stack([np.ones(len(predictions)), direction_derivative, radial_scaled])
    return predictions, jacobian


def _objective_residuals(parameters: FloatArray, system: _PreparedSystem) -> FloatArray:
    predictions, _ = _model_and_jacobian(parameters, system)
    return (system.centered_times_ns - predictions) / system.fit_scales_ns


def _objective_jacobian(parameters: FloatArray, system: _PreparedSystem) -> FloatArray:
    _, jacobian = _model_and_jacobian(parameters, system)
    return -jacobian / system.fit_scales_ns[:, None]


def _fit_from_seed(
    system: _PreparedSystem,
    parameters: FloatArray,
    options: QuadraticFrontFitOptions,
) -> OptimizeResult:
    """Fit four parameters with the physical nonnegative-curvature bound."""
    return least_squares(
        _objective_residuals,
        x0=parameters,
        jac=_objective_jacobian,
        args=(system,),
        bounds=([-np.inf, -np.inf, -np.inf, 0.0], [np.inf, np.inf, np.inf, np.inf]),
        method="trf",
        loss="linear",
        x_scale="jac",
        ftol=options.optimizer_ftol,
        xtol=options.optimizer_xtol,
        gtol=options.optimizer_gtol,
        max_nfev=options.maximum_function_evaluations,
    )


def _seed_at_direction(
    system: _PreparedSystem, sky: FloatArray, curvature_delay: float | None
) -> FloatArray:
    """Profile the time intercept and optionally estimate curvature linearly."""
    slope_x, slope_y = sky[:2] / sky[2]
    base = np.array([0.0, slope_x, slope_y, 0.0])
    planar_times, derivatives = _model_and_jacobian(base, system)
    residual_times = system.centered_times_ns - planar_times
    radial_scaled = derivatives[:, 3]
    inverse_scales = 1.0 / system.fit_scales_ns
    if curvature_delay is None:
        design = np.column_stack([np.ones(len(residual_times)), radial_scaled])
        solution = np.linalg.lstsq(
            design * inverse_scales[:, None], residual_times * inverse_scales, rcond=None
        )[0]
        curvature_delay = max(0.0, float(solution[1]))
    # Normalize weights before squaring: preserve ratios without overflow.
    weights = (inverse_scales / np.max(inverse_scales)) ** 2
    time_offset = float(
        np.average(residual_times - curvature_delay * radial_scaled, weights=weights)
    )
    return np.array([time_offset, slope_x, slope_y, curvature_delay])


def _build_seeds(
    positions: FloatArray,
    uncertainties: FloatArray,
    system: _PreparedSystem,
    weighting: WeightingMode,
    options: QuadraticFrontFitOptions,
) -> tuple[list[tuple[str, FloatArray]], tuple[str, ...], float | None]:
    """Use measured-data plane directions plus an independent vertical fallback."""
    directions: list[tuple[str, FloatArray]] = []
    messages: list[str] = []
    plane_objective = None
    try:
        # Convert even ancillary plane-diagnostic overflows into a recorded
        # initializer failure, leaving the independent vertical starts available.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            plane = fit_plane_front(
                positions,
                system.centered_times_ns,
                uncertainties,
                weighting=weighting,
                options=PlaneFrontFitOptions(minimum_stations=options.minimum_stations),
            )
        if plane.sky_direction[2] > options.minimum_sky_z_for_slopes:
            directions.append(("plane", plane.sky_direction))
            zero_seed = _seed_at_direction(system, plane.sky_direction, 0.0)
            residuals = _objective_residuals(zero_seed, system)
            plane_objective = float(residuals @ residuals)
        else:
            messages.append("Plane initializer rejected: direction too close to horizon.")
    except _NUMERICAL_ERRORS as error:
        messages.append(f"Plane initialization failed: {type(error).__name__}: {error}")
    directions.append(("vertical", np.array([0.0, 0.0, 1.0])))
    seeds: list[tuple[str, FloatArray]] = []
    for direction_label, sky in directions:
        choices = [("linear_curvature", None), ("zero_curvature", 0.0)]
        choices.extend(
            (f"positive_curvature_{index}", float(delay))
            for index, delay in enumerate(options.positive_curvature_seeds_ns)
        )
        for suffix, delay in choices:
            label = f"{direction_label}:{suffix}"
            try:
                parameters = _seed_at_direction(system, sky, delay)
                if not np.isfinite(parameters).all():
                    raise ValueError("Initializer parameters are not finite.")
            except _NUMERICAL_ERRORS as error:
                messages.append(f"{label}: {type(error).__name__}: {error}")
                continue
            if not any(np.array_equal(parameters, old) for _, old in seeds):
                seeds.append((label, parameters))
    return seeds, tuple(messages), plane_objective


def _attempt_from_exception(label: str, error: Exception) -> OptimizerAttempt:
    return OptimizerAttempt(
        initializer=label,
        accepted=False,
        scipy_success=False,
        status=None,
        message=str(error),
        objective_sum_squares=None,
        scipy_cost=None,
        optimality=None,
        function_evaluations=None,
        jacobian_evaluations=None,
        active_mask=None,
        final_parameters=None,
        exception_type=type(error).__name__,
    )


def _attempt_from_optimizer(
    label: str, optimizer: OptimizeResult, system: _PreparedSystem
) -> OptimizerAttempt:
    """Re-evaluate the objective; do not trust malformed or nonfinite solver output."""
    parameters = np.asarray(optimizer.x, dtype=np.float64)
    finite = parameters.shape == (4,) and bool(np.isfinite(parameters).all())
    objective = None
    if finite and parameters[3] >= 0.0:
        residuals = _objective_residuals(parameters, system)
        objective = float(residuals @ residuals)
        finite = np.isfinite(objective)
    else:
        finite = False
    finite = finite and bool(np.isfinite([optimizer.cost, optimizer.optimality]).all())
    return OptimizerAttempt(
        initializer=label,
        accepted=bool(optimizer.success and finite),
        scipy_success=bool(optimizer.success),
        status=int(optimizer.status),
        message=str(optimizer.message),
        objective_sum_squares=objective if finite else None,
        scipy_cost=float(optimizer.cost) if np.isfinite(optimizer.cost) else None,
        optimality=float(optimizer.optimality) if np.isfinite(optimizer.optimality) else None,
        function_evaluations=int(optimizer.nfev),
        jacobian_evaluations=None if optimizer.njev is None else int(optimizer.njev),
        active_mask=tuple(int(value) for value in optimizer.active_mask),
        final_parameters=tuple(float(value) for value in parameters) if finite else None,
        exception_type=None,
    )


def _jacobian_diagnostics(jacobian: FloatArray, tolerance: float) -> tuple[int, float, FloatArray]:
    """Diagnose independent parameter effects after removing column unit scales."""
    column_norms = np.hypot.reduce(jacobian, axis=0)
    normalized = np.divide(
        jacobian, column_norms, out=np.zeros_like(jacobian), where=column_norms > 0.0
    )
    singular_values = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.count_nonzero(singular_values > tolerance * singular_values[0]))
    condition = (
        float(singular_values[0] / singular_values[-1])
        if singular_values[-1] > 0.0
        else float("inf")
    )
    return rank, condition, singular_values


def fit_quadratic_front(
    station_positions_m: ArrayLike,
    observed_times_ns: ArrayLike,
    timing_uncertainties_ns: ArrayLike,
    *,
    core_position_m: ArrayLike,
    weighting: WeightingMode = "timing",
    options: QuadraticFrontFitOptions | None = None,
) -> QuadraticFrontFitResult:
    r"""Fit a downward direction, core time, and nonnegative quadratic curvature.

    The fixed-core timing equation is t_i = t_c + d_i.u/c + k rho_i^2, with
    d_i = r_i - r_c and rho_i = |d_i - (d_i.u)u|. Both u and rho_i are recomputed
    at each trial. The optimizer receives only measurements and the stated core,
    never generated directions or true curvature. All outputs are copies.

    ``timing`` minimizes sum((observed-predicted)/sigma)^2. ``uniform`` minimizes
    unscaled timing SSE, but its reported chi-square still uses physical sigma.
    The nonnegative boundary and nonlinear direction make N-4 a *nominal*
    residual degree count; near-boundary comparisons require simulation.

    A known true core isolates fitting correctness. A core supplied from another
    reconstruction makes this method explicitly core-assisted. This API does
    not estimate the core, flatten times, implement Earth-curvature corrections,
    or reproduce the complete Pierre Auger reconstruction.
    """
    fit_options = options if options is not None else QuadraticFrontFitOptions()
    if not isinstance(fit_options, QuadraticFrontFitOptions):
        raise TypeError("options must be QuadraticFrontFitOptions or None.")
    positions, times, uncertainties, core = _validate_inputs(
        station_positions_m,
        observed_times_ns,
        timing_uncertainties_ns,
        core_position_m,
        fit_options,
    )
    system = _prepare_system(positions, times, uncertainties, core, weighting)
    seeds, initialization_messages, plane_objective = _build_seeds(
        positions, uncertainties, system, weighting, fit_options
    )
    if not seeds:
        raise QuadraticFrontGeometryError(
            "No finite initializer could be constructed: " + "; ".join(initialization_messages)
        )
    attempts: list[OptimizerAttempt] = []
    successful: list[tuple[str, OptimizeResult, OptimizerAttempt]] = []
    for label, parameters in seeds:
        try:
            optimizer = _fit_from_seed(system, parameters, fit_options)
            attempt = _attempt_from_optimizer(label, optimizer, system)
        except _NUMERICAL_ERRORS as error:
            attempts.append(_attempt_from_exception(label, error))
            continue
        attempts.append(attempt)
        if attempt.accepted:
            successful.append((label, optimizer, attempt))
    if not successful:
        raise QuadraticFrontOptimizationError(
            "Every quadratic-front optimizer start failed.", tuple(attempts)
        )
    label, best, best_attempt = min(successful, key=lambda item: item[2].objective_sum_squares)
    objective = float(best_attempt.objective_sum_squares)
    if plane_objective is not None and objective > (
        plane_objective
        + fit_options.nested_objective_absolute_tolerance
        + fit_options.nested_objective_relative_tolerance * plane_objective
    ):
        raise QuadraticFrontOptimizationError(
            "Curved objective exceeds its feasible zero-curvature plane initializer.",
            tuple(attempts),
        )
    jacobian = _objective_jacobian(best.x, system)
    rank, condition, singular_values = _jacobian_diagnostics(
        jacobian, fit_options.jacobian_rank_relative_tolerance
    )
    if rank < 4:
        raise QuadraticFrontGeometryError(
            "The final timing Jacobian cannot identify all four fitted parameters.", tuple(attempts)
        )
    sky, _ = _sky_and_derivatives(best.x[1], best.x[2])
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            predictions_centered, _ = _model_and_jacobian(best.x, system)
            predicted = predictions_centered + system.time_origin_ns
            core_time = float(system.time_origin_ns + best.x[0])
            # Keep residual arithmetic on the same centered scale as the optimizer.
            residuals = system.centered_times_ns - predictions_centered
            standardized = residuals / uncertainties
            objective_residuals = residuals / system.fit_scales_ns
            chi_square = float(standardized @ standardized)
            residual_sum_squares = float(residuals @ residuals)
            objective_sum_squares = float(objective_residuals @ objective_residuals)
        final_values = np.concatenate(
            [
                predicted,
                residuals,
                standardized,
                objective_residuals,
                [core_time, chi_square, residual_sum_squares, objective_sum_squares],
            ]
        )
        if not np.isfinite(final_values).all():
            raise FloatingPointError("Final predictions or diagnostics are not finite.")
    except FloatingPointError as error:
        raise QuadraticFrontOptimizationError(
            "Final fit diagnostics exceed finite float64 arithmetic.", tuple(attempts)
        ) from error
    flags = ["known_core_assisted", "nominal_degrees_of_freedom"]
    if condition >= fit_options.geometry_condition_warning_threshold:
        flags.append("ill_conditioned_final_jacobian")
    if sky[2] <= fit_options.near_horizon_sky_z_threshold:
        flags.append("near_horizon_slope_parameterization")
    if best.x[3] <= fit_options.boundary_curvature_tolerance_ns or best.active_mask[3] == -1:
        flags.extend(["curvature_at_lower_bound", "reduced_chi_square_nominal_boundary"])
    horizontal_norm = float(np.hypot(sky[0], sky[1]))
    if horizontal_norm <= fit_options.vertical_azimuth_tolerance:
        azimuth_deg = float("nan")
        flags.append("azimuth_undefined_near_vertical")
    else:
        azimuth_deg = float(np.rad2deg(np.arctan2(sky[1], sky[0])) % 360.0)
    if any(not attempt.accepted for attempt in attempts):
        flags.append("some_optimizer_starts_failed")
    if initialization_messages:
        flags.append("some_initializers_unavailable")
    degrees_of_freedom = len(times) - 4
    return QuadraticFrontFitResult(
        weighting=weighting,
        options=fit_options,
        number_of_stations=len(times),
        core_position_m=_readonly(core),
        core_time_ns=core_time,
        time_origin_ns=system.time_origin_ns,
        curvature_ns_per_m2=float(best.x[3] / REFERENCE_DISTANCE_SQUARED_M2),
        delay_at_1km_ns=float(best.x[3]),
        sky_direction=_readonly(sky),
        propagation_direction=_readonly(-sky),
        zenith_deg=float(np.rad2deg(np.arctan2(horizontal_norm, sky[2]))),
        azimuth_deg=azimuth_deg,
        predicted_times_ns=_readonly(predicted),
        residuals_ns=_readonly(residuals),
        objective_residuals=_readonly(objective_residuals),
        standardized_residuals=_readonly(standardized),
        objective_sum_squares=objective_sum_squares,
        residual_sum_squares_ns2=residual_sum_squares,
        chi_square=chi_square,
        degrees_of_freedom=degrees_of_freedom,
        reduced_chi_square=chi_square / degrees_of_freedom,
        rms_residual_ns=float(np.sqrt(residual_sum_squares / len(times))),
        maximum_absolute_residual_ns=float(np.max(np.abs(residuals))),
        final_jacobian_rank=rank,
        final_jacobian_condition_number=condition,
        final_jacobian_singular_values=_readonly(singular_values),
        initializer_used=label,
        initialization_messages=initialization_messages,
        optimizer_attempts=tuple(attempts),
        quality_flags=tuple(flags),
        optimizer_status=int(best.status),
        optimizer_message=str(best.message),
        optimizer_function_evaluations=int(best.nfev),
        optimizer_jacobian_evaluations=best_attempt.jacobian_evaluations,
        optimizer_cost=float(best.cost),
        optimizer_optimality=float(best.optimality),
        optimizer_active_mask=tuple(int(value) for value in best.active_mask),
        optimizer_parameters=tuple(float(value) for value in best.x),
        plane_objective_sum_squares=plane_objective,
    )
