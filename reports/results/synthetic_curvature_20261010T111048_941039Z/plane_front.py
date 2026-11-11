"""Uncertainty-aware plane-front reconstruction for surface-detector timings.

The fitter centres and whitens station measurements, uses an SVD to diagnose the
detector geometry and construct physical starting directions, then minimizes timing
residuals over a downward unit-vector parameterization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import OptimizeResult, least_squares

type FloatArray = NDArray[np.float64]
type WeightingMode = Literal["timing", "uniform"]
type OptimizerMethod = Literal["trf", "dogbox", "lm"]

C_M_PER_NS = 0.299_792_458


@dataclass(frozen=True, slots=True)
class PlaneFrontFitOptions:
    """Recorded numerical and scientific settings for one reconstruction."""

    minimum_stations: int = 4
    surface_seed_margin: float = 1.0e-6
    vertical_azimuth_tolerance: float = 1.0e-12
    planarity_ratio_threshold: float = 0.05
    surface_condition_warning_threshold: float = 1.0e8
    minimum_sky_z_for_slopes: float = 1.0e-12
    near_horizon_sky_z_threshold: float = 1.0e-2
    optimizer_method: OptimizerMethod = "trf"
    optimizer_loss: str = "linear"
    optimizer_ftol: float = 1.0e-10
    optimizer_xtol: float = 1.0e-10
    optimizer_gtol: float = 1.0e-10
    maximum_function_evaluations: int = 2_000

    def __post_init__(self) -> None:
        if self.minimum_stations < 4:
            raise ValueError("minimum_stations must be at least four.")
        if not 0.0 < self.surface_seed_margin < 1.0:
            raise ValueError("surface_seed_margin must lie between zero and one.")
        if not 0.0 < self.vertical_azimuth_tolerance < 1.0:
            raise ValueError("vertical_azimuth_tolerance must lie between zero and one.")
        if not 0.0 <= self.planarity_ratio_threshold <= 1.0:
            raise ValueError("planarity_ratio_threshold must lie between zero and one.")
        if self.surface_condition_warning_threshold < 1.0:
            raise ValueError("surface_condition_warning_threshold must be at least one.")
        if not 0.0 < self.minimum_sky_z_for_slopes < 1.0:
            raise ValueError("minimum_sky_z_for_slopes must lie between zero and one.")
        if not self.minimum_sky_z_for_slopes < self.near_horizon_sky_z_threshold < 1.0:
            raise ValueError(
                "near_horizon_sky_z_threshold must exceed minimum_sky_z_for_slopes "
                "and remain below one."
            )
        for name, value in (
            ("optimizer_ftol", self.optimizer_ftol),
            ("optimizer_xtol", self.optimizer_xtol),
            ("optimizer_gtol", self.optimizer_gtol),
        ):
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and strictly positive.")
        if not self.optimizer_loss:
            raise ValueError("optimizer_loss must not be empty.")
        if self.maximum_function_evaluations < 1:
            raise ValueError("maximum_function_evaluations must be positive.")


@dataclass(frozen=True, slots=True)
class OptimizerAttempt:
    """Diagnostics retained for one nonlinear-optimizer starting point."""

    initializer: str
    accepted: bool
    scipy_success: bool
    status: int | None
    message: str
    objective_sum_squares: float | None
    scipy_cost: float | None
    optimality: float | None
    function_evaluations: int | None
    jacobian_evaluations: int | None
    active_mask: tuple[int, ...] | None
    final_parameters: tuple[float, ...] | None
    exception_type: str | None


class DegenerateStationGeometryError(ValueError):
    """Raised when station positions do not span a reconstructable surface."""


class PlaneFrontInitializationError(RuntimeError):
    """Raised when no finite downward optimizer initializer can be constructed."""

    def __init__(self, message: str, rejected_initializers: tuple[str, ...]) -> None:
        super().__init__(message)
        self.rejected_initializers = rejected_initializers


class PlaneFrontOptimizationError(RuntimeError):
    """Raised when all physically valid optimizer starts fail."""

    def __init__(self, message: str, attempts: tuple[OptimizerAttempt, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True, slots=True)
class PlaneFrontFitResult:
    """Successful plane-front reconstruction and its scientific diagnostics."""

    weighting: WeightingMode
    options: PlaneFrontFitOptions
    number_of_stations: int

    sky_direction: FloatArray
    propagation_direction: FloatArray
    zenith_deg: float
    azimuth_deg: float

    reference_position_m: FloatArray
    reference_time_ns: float
    origin_time_ns: float

    predicted_times_ns: FloatArray
    residuals_ns: FloatArray
    objective_residuals: FloatArray
    standardized_residuals: FloatArray

    # For timing weighting, objective_sum_squares equals chi_square. For uniform
    # weighting it equals raw timing SSE numerically, while chi_square remains a
    # separate uncertainty-standardized diagnostic that the fit did not minimize.
    objective_sum_squares: float
    residual_sum_squares_ns2: float
    chi_square: float
    degrees_of_freedom: int
    reduced_chi_square: float
    rms_residual_ns: float
    maximum_absolute_residual_ns: float

    full_geometry_rank: int
    surface_condition_number: float
    full_condition_number: float
    planarity_ratio: float
    singular_values: FloatArray
    final_jacobian_rank: int

    initializer_used: str
    initializer_attempts: tuple[str, ...]
    initializer_rejections: tuple[str, ...]
    optimizer_attempts: tuple[OptimizerAttempt, ...]
    quality_flags: tuple[str, ...]

    optimizer_status: int
    optimizer_message: str
    optimizer_function_evaluations: int
    optimizer_jacobian_evaluations: int | None
    optimizer_cost: float
    optimizer_optimality: float
    optimizer_active_mask: tuple[int, ...]
    optimizer_parameters: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class _PreparedSystem:
    positions_m: FloatArray
    times_ns: FloatArray
    uncertainties_ns: FloatArray
    fit_scales_ns: FloatArray

    reference_position_m: FloatArray
    reference_time_ns: float

    whitened_design: FloatArray
    whitened_times: FloatArray
    left_vectors: FloatArray
    singular_values: FloatArray
    right_vectors_transposed: FloatArray

    rank: int
    surface_condition_number: float
    full_condition_number: float
    planarity_ratio: float
    quality_flags: tuple[str, ...]


def _readonly_float_array(values: ArrayLike) -> FloatArray:
    result = np.array(values, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _unit_vector(vector: ArrayLike, *, name: str) -> FloatArray:
    result = np.asarray(vector, dtype=np.float64)
    if result.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), but has shape {result.shape}.")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values.")

    norm = float(np.linalg.norm(result))
    if norm <= 0.0:
        raise ValueError(f"{name} must be nonzero, but has norm {norm}.")
    return result / norm


def sky_direction_from_angles(zenith_rad: float, azimuth_rad: float) -> FloatArray:
    """Convert sky-arrival zenith and azimuth into an upward unit vector."""

    if not np.isfinite([zenith_rad, azimuth_rad]).all():
        raise ValueError("Zenith and azimuth must be finite.")
    if not 0.0 <= zenith_rad <= np.pi / 2.0:
        raise ValueError("Zenith must lie between zero and pi/2 radians.")

    return np.array(
        [
            np.sin(zenith_rad) * np.cos(azimuth_rad),
            np.sin(zenith_rad) * np.sin(azimuth_rad),
            np.cos(zenith_rad),
        ],
        dtype=np.float64,
    )


def propagation_direction_from_angles(zenith_rad: float, azimuth_rad: float) -> FloatArray:
    """Convert sky-arrival angles into the opposite propagation vector."""

    return -sky_direction_from_angles(zenith_rad, azimuth_rad)


def angular_separation_deg(first_vector: ArrayLike, second_vector: ArrayLike) -> float:
    """Calculate the physical angle between two directions in degrees."""

    first = _unit_vector(first_vector, name="first_vector")
    second = _unit_vector(second_vector, name="second_vector")
    cross_norm = float(np.linalg.norm(np.cross(first, second)))
    dot_product = float(np.clip(np.dot(first, second), -1.0, 1.0))
    return float(np.rad2deg(np.arctan2(cross_norm, dot_product)))


def _predict_station_times_unchecked(
    reference_time_ns: float,
    propagation_direction: FloatArray,
    station_positions_m: FloatArray,
    reference_position_m: FloatArray,
) -> FloatArray:
    centered_positions_m = station_positions_m - reference_position_m
    geometric_delays_ns = centered_positions_m @ propagation_direction / C_M_PER_NS
    return reference_time_ns + geometric_delays_ns


def predict_station_times_ns(
    reference_time_ns: float,
    propagation_direction: ArrayLike,
    station_positions_m: ArrayLike,
    reference_position_m: ArrayLike,
) -> FloatArray:
    """Evaluate the plane-front timing equation after validating public inputs."""

    positions = np.asarray(station_positions_m, dtype=np.float64)
    reference = np.asarray(reference_position_m, dtype=np.float64)
    direction = _unit_vector(propagation_direction, name="propagation_direction")

    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            f"station_positions_m must have shape (N, 3), but has shape {positions.shape}."
        )
    if reference.shape != (3,):
        raise ValueError(
            f"reference_position_m must have shape (3,), but has shape {reference.shape}."
        )
    if not np.isfinite(positions).all() or not np.isfinite(reference).all():
        raise ValueError("Station and reference positions must be finite.")
    if not np.isfinite(reference_time_ns):
        raise ValueError("reference_time_ns must be finite.")

    return _predict_station_times_unchecked(
        float(reference_time_ns),
        direction,
        positions,
        reference,
    )


def _validate_measurements(
    station_positions_m: ArrayLike,
    observed_times_ns: ArrayLike,
    timing_uncertainties_ns: ArrayLike,
    options: PlaneFrontFitOptions,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    positions = np.array(station_positions_m, dtype=np.float64, copy=True)
    times = np.array(observed_times_ns, dtype=np.float64, copy=True)
    uncertainties = np.array(timing_uncertainties_ns, dtype=np.float64, copy=True)

    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("station_positions_m must have shape (N, 3).")

    number_of_stations = positions.shape[0]
    if number_of_stations < options.minimum_stations:
        raise ValueError(f"At least {options.minimum_stations} stations are required.")
    if times.shape != (number_of_stations,):
        raise ValueError("observed_times_ns must have shape (N,).")
    if uncertainties.shape != (number_of_stations,):
        raise ValueError("timing_uncertainties_ns must have shape (N,).")
    if not np.isfinite(positions).all():
        raise ValueError("Station positions must be finite.")
    if not np.isfinite(times).all():
        raise ValueError("Observed times must be finite.")
    if not np.isfinite(uncertainties).all():
        raise ValueError("Timing uncertainties must be finite.")
    if (uncertainties <= 0.0).any():
        raise ValueError("Timing uncertainties must be strictly positive.")

    return positions, times, uncertainties


def _svd_rank(singular_values: FloatArray, matrix_shape: tuple[int, int]) -> int:
    if singular_values.size == 0 or singular_values[0] <= 0.0:
        return 0
    tolerance = max(matrix_shape) * np.finfo(np.float64).eps * singular_values[0]
    return int(np.count_nonzero(singular_values > tolerance))


def _prepare_system(
    positions_m: FloatArray,
    times_ns: FloatArray,
    uncertainties_ns: FloatArray,
    weighting: WeightingMode,
    options: PlaneFrontFitOptions,
) -> _PreparedSystem:
    """Centre and whiten measurements, then diagnose geometry with an SVD."""

    if weighting == "timing":
        fit_scales_ns = uncertainties_ns.copy()
    elif weighting == "uniform":
        fit_scales_ns = np.ones_like(uncertainties_ns)
    else:
        raise ValueError("weighting must be either 'timing' or 'uniform'.")

    weights = 1.0 / fit_scales_ns**2
    reference_position_m = np.average(positions_m, axis=0, weights=weights)
    reference_time_ns = float(np.average(times_ns, weights=weights))
    centered_positions_m = positions_m - reference_position_m
    centered_times_ns = times_ns - reference_time_ns
    design_matrix_ns = centered_positions_m / C_M_PER_NS
    square_root_weights = np.sqrt(weights)
    whitened_design = design_matrix_ns * square_root_weights[:, np.newaxis]
    whitened_times = centered_times_ns * square_root_weights

    left_vectors, singular_values, right_vectors_transposed = np.linalg.svd(
        whitened_design,
        full_matrices=False,
    )
    rank = _svd_rank(singular_values, whitened_design.shape)
    if rank < 2:
        raise DegenerateStationGeometryError(
            "Station geometry must span at least two independent spatial directions."
        )

    surface_condition_number = float(singular_values[0] / singular_values[1])
    full_condition_number = (
        float(singular_values[0] / singular_values[2]) if rank == 3 else float("inf")
    )
    planarity_ratio = (
        float(singular_values[2] / singular_values[1]) if singular_values.size >= 3 else 0.0
    )

    flags: list[str] = []
    duplicate_count = len(positions_m) - len(np.unique(positions_m, axis=0))
    if duplicate_count:
        flags.append(f"duplicate_station_positions:{duplicate_count}")
    if rank == 2:
        flags.append("rank_two_surface_geometry")
    if planarity_ratio < options.planarity_ratio_threshold:
        flags.append("surface_like_geometry")
    if surface_condition_number > options.surface_condition_warning_threshold:
        flags.append("ill_conditioned_surface_geometry")

    return _PreparedSystem(
        positions_m=positions_m,
        times_ns=times_ns,
        uncertainties_ns=uncertainties_ns,
        fit_scales_ns=fit_scales_ns,
        reference_position_m=reference_position_m,
        reference_time_ns=reference_time_ns,
        whitened_design=whitened_design,
        whitened_times=whitened_times,
        left_vectors=left_vectors,
        singular_values=singular_values,
        right_vectors_transposed=right_vectors_transposed,
        rank=rank,
        surface_condition_number=surface_condition_number,
        full_condition_number=full_condition_number,
        planarity_ratio=planarity_ratio,
        quality_flags=tuple(flags),
    )


def _truncated_linear_solution(system: _PreparedSystem, components: int) -> FloatArray:
    """Solve the weighted timing equation in a selected SVD subspace."""

    projected_times = system.left_vectors[:, :components].T @ system.whitened_times
    coefficients = projected_times / system.singular_values[:components]
    return system.right_vectors_transposed[:components].T @ coefficients


def _downward_from_horizontal(vector: FloatArray, *, margin: float) -> FloatArray:
    """Project an x-y estimate inside the unit disk and recover its negative z."""

    horizontal = np.asarray(vector[:2], dtype=np.float64)
    horizontal_norm = float(np.linalg.norm(horizontal))
    maximum_horizontal_norm = 1.0 - margin
    if horizontal_norm > maximum_horizontal_norm:
        horizontal = horizontal * maximum_horizontal_norm / horizontal_norm

    vertical = -np.sqrt(max(0.0, 1.0 - float(np.dot(horizontal, horizontal))))
    return np.array([horizontal[0], horizontal[1], vertical], dtype=np.float64)


def _deduplicate_seeds(
    seeds: list[tuple[str, FloatArray]],
) -> tuple[list[tuple[str, FloatArray]], tuple[str, ...]]:
    unique: list[tuple[str, FloatArray]] = []
    rejected: list[str] = []

    for label, candidate in seeds:
        try:
            unit_candidate = _unit_vector(candidate, name=f"initializer {label}")
        except ValueError as error:
            rejected.append(f"{label}:invalid:{error}")
            continue

        if unit_candidate[2] >= 0.0:
            rejected.append(f"{label}:not_downward")
            continue
        if any(
            np.allclose(unit_candidate, previous, rtol=0.0, atol=1.0e-10) for _, previous in unique
        ):
            rejected.append(f"{label}:duplicate")
            continue
        unique.append((label, unit_candidate))

    return unique, tuple(rejected)


def _build_propagation_seeds(
    system: _PreparedSystem,
    options: PlaneFrontFitOptions,
) -> tuple[list[tuple[str, FloatArray]], tuple[str, ...], tuple[str, ...]]:
    """Build distinct downward optimizer seeds from rank-two and rank-three fits."""

    seeds: list[tuple[str, FloatArray]] = []
    flags: list[str] = list(system.quality_flags)

    surface_component = _truncated_linear_solution(system, components=2)
    surface_norm = float(np.linalg.norm(surface_component))
    if surface_norm >= 1.0:
        surface_component *= (1.0 - options.surface_seed_margin) / surface_norm
        flags.append("projected_superluminal_surface_seed")

    plane_normal = system.right_vectors_transposed[2]
    missing_component = np.sqrt(max(0.0, 1.0 - float(np.dot(surface_component, surface_component))))
    seeds.append(("surface_plus", surface_component + missing_component * plane_normal))
    seeds.append(("surface_minus", surface_component - missing_component * plane_normal))

    if system.rank == 3:
        full_solution = _truncated_linear_solution(system, components=3)
        full_norm = float(np.linalg.norm(full_solution))
        if np.isfinite(full_norm) and full_norm > 0.0:
            seeds.append(("full_3d", full_solution / full_norm))

    seeds.append(
        (
            "horizontal_fallback",
            _downward_from_horizontal(surface_component, margin=options.surface_seed_margin),
        )
    )
    seeds.append(("vertical_fallback", np.array([0.0, 0.0, -1.0])))

    unique, rejected = _deduplicate_seeds(seeds)
    if not unique:
        raise PlaneFrontInitializationError(
            "No finite downward initialization could be built.",
            rejected_initializers=rejected,
        )
    if sum(label.startswith("surface_") for label, _ in unique) > 1:
        flags.append("multiple_downward_surface_branches")
    return unique, tuple(dict.fromkeys(flags)), rejected


def _sky_direction_from_slopes(
    horizontal_slope_x: float,
    horizontal_slope_y: float,
) -> FloatArray:
    """Map finite slopes to 0 <= zenith < 90 degrees; the horizon is excluded."""

    if not np.isfinite([horizontal_slope_x, horizontal_slope_y]).all():
        raise ValueError("Sky slopes must be finite.")
    normalizer = np.hypot(np.hypot(horizontal_slope_x, horizontal_slope_y), 1.0)
    return np.array(
        [
            horizontal_slope_x / normalizer,
            horizontal_slope_y / normalizer,
            1.0 / normalizer,
        ],
        dtype=np.float64,
    )


def _slopes_from_propagation(
    propagation_direction: FloatArray,
    *,
    minimum_sky_z: float,
) -> tuple[float, float]:
    """Convert a downward propagation seed to unconstrained upper-sky slopes."""

    unit_propagation = _unit_vector(
        propagation_direction,
        name="propagation initializer",
    )
    if unit_propagation[2] >= 0.0:
        raise ValueError("A propagation initializer must point downward.")

    sky_direction = -unit_propagation
    if sky_direction[2] <= minimum_sky_z:
        raise ValueError("A propagation initializer is too close to the horizon for slopes.")
    return (
        float(sky_direction[0] / sky_direction[2]),
        float(sky_direction[1] / sky_direction[2]),
    )


def _objective_residuals(parameters: FloatArray, system: _PreparedSystem) -> FloatArray:
    """Evaluate the residual vector minimized by SciPy's least-squares solver."""

    time_offset_ns, horizontal_slope_x, horizontal_slope_y = parameters
    sky_direction = _sky_direction_from_slopes(horizontal_slope_x, horizontal_slope_y)
    propagation_direction = -sky_direction
    reference_time_ns = system.reference_time_ns + time_offset_ns
    predicted_times_ns = _predict_station_times_unchecked(
        reference_time_ns,
        propagation_direction,
        system.positions_m,
        system.reference_position_m,
    )
    return (system.times_ns - predicted_times_ns) / system.fit_scales_ns


def _fit_from_seed(
    system: _PreparedSystem,
    propagation_seed: FloatArray,
    options: PlaneFrontFitOptions,
) -> OptimizeResult:
    """Run one nonlinear optimization attempt from a propagation seed."""

    horizontal_slope_x, horizontal_slope_y = _slopes_from_propagation(
        propagation_seed,
        minimum_sky_z=options.minimum_sky_z_for_slopes,
    )
    initial_parameters = np.array(
        [0.0, horizontal_slope_x, horizontal_slope_y],
        dtype=np.float64,
    )
    return least_squares(
        _objective_residuals,
        x0=initial_parameters,
        args=(system,),
        method=options.optimizer_method,
        loss=options.optimizer_loss,
        x_scale="jac",
        ftol=options.optimizer_ftol,
        xtol=options.optimizer_xtol,
        gtol=options.optimizer_gtol,
        max_nfev=options.maximum_function_evaluations,
    )


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _attempt_from_optimizer(label: str, optimizer: OptimizeResult) -> OptimizerAttempt:
    parameters = np.asarray(optimizer.x, dtype=np.float64)
    residuals = np.asarray(optimizer.fun, dtype=np.float64)
    values_are_finite = np.isfinite(parameters).all() and np.isfinite(residuals).all()
    accepted = bool(optimizer.success and values_are_finite)
    active_mask_value = getattr(optimizer, "active_mask", None)
    active_mask = (
        tuple(int(value) for value in np.asarray(active_mask_value).ravel())
        if active_mask_value is not None
        else None
    )
    return OptimizerAttempt(
        initializer=label,
        accepted=accepted,
        scipy_success=bool(optimizer.success),
        status=int(optimizer.status),
        message=str(optimizer.message),
        objective_sum_squares=(float(np.sum(residuals**2)) if values_are_finite else None),
        scipy_cost=_optional_float(getattr(optimizer, "cost", None)),
        optimality=_optional_float(getattr(optimizer, "optimality", None)),
        function_evaluations=_optional_int(getattr(optimizer, "nfev", None)),
        jacobian_evaluations=_optional_int(getattr(optimizer, "njev", None)),
        active_mask=active_mask,
        final_parameters=(
            tuple(float(value) for value in parameters) if values_are_finite else None
        ),
        exception_type=None,
    )


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


def _jacobian_rank(jacobian: FloatArray) -> int:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    return _svd_rank(singular_values, jacobian.shape)


def fit_plane_front(
    station_positions_m: ArrayLike,
    observed_times_ns: ArrayLike,
    timing_uncertainties_ns: ArrayLike,
    *,
    weighting: WeightingMode = "timing",
    options: PlaneFrontFitOptions | None = None,
) -> PlaneFrontFitResult:
    """Reconstruct a plane front for the upper sky hemisphere (zenith < 90 degrees)."""

    fit_options = options if options is not None else PlaneFrontFitOptions()
    positions, times, uncertainties = _validate_measurements(
        station_positions_m,
        observed_times_ns,
        timing_uncertainties_ns,
        fit_options,
    )
    system = _prepare_system(
        positions,
        times,
        uncertainties,
        weighting,
        fit_options,
    )
    seeds, quality_flags, initializer_rejections = _build_propagation_seeds(
        system,
        fit_options,
    )

    successful_fits: list[tuple[str, OptimizeResult, OptimizerAttempt]] = []
    attempts: list[OptimizerAttempt] = []
    numerical_errors = (
        ValueError,
        RuntimeError,
        FloatingPointError,
        OverflowError,
        np.linalg.LinAlgError,
    )

    for label, propagation_seed in seeds:
        try:
            optimizer = _fit_from_seed(system, propagation_seed, fit_options)
        except numerical_errors as error:
            attempts.append(_attempt_from_exception(label, error))
            continue

        attempt = _attempt_from_optimizer(label, optimizer)
        attempts.append(attempt)
        if attempt.accepted:
            successful_fits.append((label, optimizer, attempt))

    if not successful_fits:
        raise PlaneFrontOptimizationError(
            "Every plane-front optimizer start failed.",
            attempts=tuple(attempts),
        )

    initializer_used, best_optimizer, best_attempt = min(
        successful_fits,
        key=lambda item: float(item[2].objective_sum_squares),
    )
    fitted_time_offset_ns, fitted_slope_x, fitted_slope_y = best_optimizer.x
    sky_direction = _sky_direction_from_slopes(fitted_slope_x, fitted_slope_y)
    propagation_direction = -sky_direction
    reference_time_ns = system.reference_time_ns + float(fitted_time_offset_ns)
    predicted_times_ns = _predict_station_times_unchecked(
        reference_time_ns,
        propagation_direction,
        positions,
        system.reference_position_m,
    )
    residuals_ns = times - predicted_times_ns
    objective_residuals = residuals_ns / system.fit_scales_ns
    standardized_residuals = residuals_ns / uncertainties
    objective_sum_squares = float(np.sum(objective_residuals**2))
    residual_sum_squares_ns2 = float(np.sum(residuals_ns**2))
    chi_square = float(np.sum(standardized_residuals**2))
    degrees_of_freedom = len(times) - 3

    final_jacobian_rank = _jacobian_rank(best_optimizer.jac)
    result_flags = list(quality_flags)
    if final_jacobian_rank < 3:
        reduced_chi_square = float("nan")
        result_flags.append("rank_deficient_final_jacobian")
        result_flags.append("reduced_chi_square_undefined_rank_deficient")
    else:
        reduced_chi_square = chi_square / degrees_of_freedom

    horizontal_sky_norm = float(np.hypot(sky_direction[0], sky_direction[1]))
    zenith_rad = float(np.arctan2(horizontal_sky_norm, sky_direction[2]))
    if horizontal_sky_norm <= fit_options.vertical_azimuth_tolerance:
        azimuth_deg = float("nan")
        result_flags.append("azimuth_undefined_near_vertical")
    else:
        azimuth_rad = float(np.arctan2(sky_direction[1], sky_direction[0]) % (2.0 * np.pi))
        azimuth_deg = float(np.rad2deg(azimuth_rad))

    if sky_direction[2] <= fit_options.near_horizon_sky_z_threshold:
        result_flags.append("near_horizon_slope_parameterization")
    failed_attempts = [attempt.initializer for attempt in attempts if not attempt.accepted]
    if failed_attempts:
        result_flags.append("failed_initializers:" + ",".join(failed_attempts))

    origin_time_ns = float(
        reference_time_ns - system.reference_position_m @ propagation_direction / C_M_PER_NS
    )
    optimizer_parameters = tuple(float(value) for value in best_optimizer.x)
    if len(optimizer_parameters) != 3:
        raise PlaneFrontOptimizationError(
            "The selected optimizer returned an unexpected parameter count.",
            attempts=tuple(attempts),
        )

    return PlaneFrontFitResult(
        weighting=weighting,
        options=fit_options,
        number_of_stations=len(times),
        sky_direction=_readonly_float_array(sky_direction),
        propagation_direction=_readonly_float_array(propagation_direction),
        zenith_deg=float(np.rad2deg(zenith_rad)),
        azimuth_deg=azimuth_deg,
        reference_position_m=_readonly_float_array(system.reference_position_m),
        reference_time_ns=reference_time_ns,
        origin_time_ns=origin_time_ns,
        predicted_times_ns=_readonly_float_array(predicted_times_ns),
        residuals_ns=_readonly_float_array(residuals_ns),
        objective_residuals=_readonly_float_array(objective_residuals),
        standardized_residuals=_readonly_float_array(standardized_residuals),
        objective_sum_squares=objective_sum_squares,
        residual_sum_squares_ns2=residual_sum_squares_ns2,
        chi_square=chi_square,
        degrees_of_freedom=degrees_of_freedom,
        reduced_chi_square=reduced_chi_square,
        rms_residual_ns=float(np.sqrt(np.mean(residuals_ns**2))),
        maximum_absolute_residual_ns=float(np.max(np.abs(residuals_ns))),
        full_geometry_rank=system.rank,
        surface_condition_number=system.surface_condition_number,
        full_condition_number=system.full_condition_number,
        planarity_ratio=system.planarity_ratio,
        singular_values=_readonly_float_array(system.singular_values),
        final_jacobian_rank=final_jacobian_rank,
        initializer_used=initializer_used,
        initializer_attempts=tuple(label for label, _ in seeds),
        initializer_rejections=initializer_rejections,
        optimizer_attempts=tuple(attempts),
        quality_flags=tuple(dict.fromkeys(result_flags)),
        optimizer_status=int(best_optimizer.status),
        optimizer_message=str(best_optimizer.message),
        optimizer_function_evaluations=int(best_optimizer.nfev),
        optimizer_jacobian_evaluations=best_attempt.jacobian_evaluations,
        optimizer_cost=float(best_optimizer.cost),
        optimizer_optimality=float(best_optimizer.optimality),
        optimizer_active_mask=tuple(int(value) for value in best_optimizer.active_mask),
        optimizer_parameters=(
            optimizer_parameters[0],
            optimizer_parameters[1],
            optimizer_parameters[2],
        ),
    )
