from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import OptimizeResult, least_squares\

type FloatArray = NDArray[np.float64]
type WeightingMode = Literal["timing", "uniform"]

C_M_PER_NS = 0.299792458  # speed of light in m/ns

MINIMUM_STATIONS = 4

SURFACE_SEED_MARGIN = 1.0e-6

VERTICAL_AZIMUTH_TOLERANCE = 1.0e-12

class DegenerateStationGeometryError(ValueError):
    """Raised when the station positions do not span a reconstructable surface."""

class PlaneFrontOptimizationError(RuntimeError):
    """Raised when every physically valid optimizer fails to converge to a solution."""

@dataclass(frozen = True, slots = True)
class PlaneFrontFitResult:
    """Successful plane-front reconstruction and its scientific diagnostics."""

    # Which object produced the result.
    weighting: WeightingMode
    number_of_stations: int

    # Reconstructed physical directions.
    sky_direction: FloatArray
    propagation_direction: FloatArray
    zenith_deg: float
    azimuth_deg: float

    # Reference quantities used by the centred timing equation.
    reference_position_m: FloatArray
    reference_time_ns: float
    origin_time_ns: float

    # Station-by-station predictions and errors.
    predicted_times_ns: FloatArray
    residuals_ns: FloatArray
    objective_residuals: FloatArray
    standardized_residuals: FloatArray

    #Fit-quality measurements.
    objective_sum_squares: float
    residual_sum_squares_ns2: float
    chi_square: float
    degrees_of_freedom: int
    reduced_chi_square: float
    rms_residual_ns: float
    maximum_absolute_residual_ns: float

    # Information about detector geometry and numerical conditioning.
    full_geometry_rank: int
    surface_condition_number: float
    full_condition_number: float
    planarity_ratio: float
    singular_values: FloatArray
    final_jacobian_rank: int

    # Information about initialization and potential warnings.
    initializer_used: str
    initializer_attempts: tuple[str, ...]
    quality_flags: tuple[str, ...]

    # Information reported by SciPy's non-linear optimizer.
    optimizer_status: int
    optimizer_message: str
    optimizer_function_evaluations: int

@dataclass( frozen = True, slots = True)
class _PreparedSystem:
    """Validated and centred quantities reused during optimization."""

    position_m: FloatArray
    times_ns: FloatArray
    uncertainties_ns: FloatArray
    fit_scales_ns: FloatArray

    reference_position_m:  FloatArray
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
    """Return a defensive float64 copy that callers can't modify."""
    result = np.asarray(values, dtype = np.float64, copy = True)
    result.setflags(write = False)
    return result

def _unit_vector(vector: ArrayLike, *, name: str) -> FloatArray:
    """Validate and normalize one three-dimensional direction vector."""

    result = np.asarray(vector, dtype = np.float64)    

    if result.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), but has shape {result.shape}.")

    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values.")

    norm = float(np.linalg.norm(result))

    if norm <= 0.0:
        raise ValueError(f"{name} must be non-zero, but has norm {norm}.")

    return result / norm

def sky_direction_from_angles(zenith_rad: float, azimuth_rad: float) -> FloatArray:
    """Convert sky-arrival zenith and azimuth into a unit vector"""

    if not np.isfinite([zenith_rad, azimuth_rad]).all():
        raise ValueError("Zenith and azimuth angles must be finite.")

    if not 0.0 <= zenith_rad <= np.pi / 2.0:
        raise ValueError(f"Zenith angle must be in [0, pi/2] radians, but is {zenith_rad}.")

    # x is east, y is north, and z is upward.
    return np.array(
        [
            np.sin(zenith_rad) * np.cos(azimuth_rad),
            np.sin(zenith_rad) * np.sin(azimuth_rad),
            np.cos(zenith_rad)
        ],
        dtype = np.float64
    )

def propagation_direction_from_angles(zenith_rad: float, azimuth_rad: float) -> FloatArray:
    """Convert sky-arrival angles into the opposite propagation vector."""

    return -sky_direction_from_angles(zenith_rad, azimuth_rad)

def angular_separation_deg(first_vector: ArrayLike, second_vector: ArrayLike) -> float:
    """Calculate the physical angle between two directions in degrees."""

    first = _unit_vector(first_vector, name = "first_vector")
    second = _unit_vector(second_vector, name = "second_vector")

    # atan2(||a x b||, a dot b) is stable for very small angular errors.
    cross_norm = float(np.linalg.norm(np.cross(first, second)))
    dot_product = float(np.clip(np.dot(first, second), -1.0, 1.0))

    return float(np.rad2deg(np.arctan2(cross_norm, dot_product)))

def _predict_station_times_unchecked(reference_time_ns: float,
                                     propagation_direction: FloatArray,
                                     station_positions_m: FloatArray,
                                     reference_position_m: FloatArray) -> FloatArray:
    """Evaluate the timing model after inputs have already been validated."""

    centered_positions_m = station_positions_m - reference_position_m

    # Matrix-vector multiplication performs every station's dot product at once.

    geometric_delays_ns = (centered_positions_m @ propagation_direction) / C_M_PER_NS

    return reference_time_ns + geometric_delays_ns

def predict_station_times_ns(reference_time_ns: float,
                             propagation_direction: ArrayLike,
                             station_positions_m: ArrayLike,
                             reference_position_m: ArrayLike) -> FloatArray:

    """Public, validated version of the plane-front timing equation."""

    positions = np.asarray(station_positions_m, dtype = np.float64)
    reference = np.asarray(reference_position_m, dtype = np.float64) 

    direction = _unit_vector(propagation_direction, name = "propagation_direction")

    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(f"station_positions_m must have shape (N, 3), but has shape {positions.shape}.")

    if reference.shape != (3,):
        raise ValueError(f"reference_position_m must have shape (3,), but has shape {reference.shape}.")

    if not np.isfinite(positions).all():
        raise ValueError("Station positions must be finite.")

    if not np.isfinite(reference).all():
        raise ValueError("Reference position must be finite.")

    if not np.isfinite(reference_time_ns):
        raise ValueError("reference_time_ns must be finite.")

    return _predict_station_times_unchecked(float(reference_time_ns), direction, positions, reference)

