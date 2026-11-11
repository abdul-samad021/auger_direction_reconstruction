"""Controlled quadratic-front timings for synthetic model-mismatch experiments.

This is a phenomenological timing generator, not an air-shower or detector
simulation and not an implementation of the Pierre Auger reconstruction model.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from auger_reco.physics.plane_front import C_M_PER_NS

type FloatArray = NDArray[np.float64]

# Accept floating-point roundoff in a constructed unit vector, not normalization.
UNIT_VECTOR_ATOL = 1.0e-12


def _finite_real_array(value: ArrayLike, name: str) -> FloatArray:
    """Accept real numeric data without silently discarding complex components."""
    try:
        original = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric values.") from error
    if original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numeric values, not booleans.")
    with np.errstate(over="ignore", invalid="ignore"):
        converted = np.asarray(original, dtype=np.float64)
    if not np.all(np.isfinite(converted)):
        raise ValueError(f"{name} must contain only finite float64 values.")
    return converted


def _finite_real_scalar(value: float, name: str) -> float:
    """Reject array-shaped, Boolean, complex, or non-finite scalar settings."""
    converted = _finite_real_array(value, name)
    if converted.ndim != 0:
        raise ValueError(f"{name} must be a scalar.")
    return float(converted)


def quadratic_front_times_ns(
    station_positions_m: ArrayLike,
    propagation_direction: ArrayLike,
    core_position_m: ArrayLike,
    core_time_ns: float,
    curvature_ns_per_m2: float,
) -> FloatArray:
    r"""Generate noiseless plane-plus-quadratic station arrival times.

    For a downward unit propagation vector :math:`u`, a specified point on the
    shower axis :math:`r_c`, and :math:`d_i=r_i-r_c`, the model is

    .. math::

        t_i = t_c + (d_i\cdot u)/c + k\rho_i^2,\qquad
        \rho_i = \|d_i-(d_i\cdot u)u\|.

    ``core_position_m`` is the known synthetic core on the shower axis;
    ``core_time_ns`` is the model's arrival time at that position. Positive
    ``curvature_ns_per_m2`` delays stations away from the axis relative to the
    tangent plane. Zero curvature gives the plane model exactly. ``rho`` is
    perpendicular distance to the axis, not horizontal distance to the core.

    For k > 0, R_eff = 1 / (2*c*k) is the radius associated with the *local*
    spherical-front expansion. The quadratic model is not an exact spherical
    front, and this radius is not calibrated to Auger events. The caller must
    justify any comparison to physical shower curvature separately.

    Positions must be a nonempty (N, 3) real finite array in meters. The core
    and direction must have shape (3,), and direction must have negative z
    and unit length within absolute tolerance ``UNIT_VECTOR_ATOL``. Direction
    is never silently normalized. Scalar settings must be finite and curvature
    nonnegative. Boolean/complex/string arrays are rejected. Input arrays are
    never changed. A new float64 (N,) array is returned.

    Raises
    ------
    ValueError
        For invalid inputs, or arithmetic that cannot be represented with
        finite float64 intermediate values and output.
    """
    positions = _finite_real_array(station_positions_m, "station_positions_m")
    if positions.ndim != 2 or positions.shape[1] != 3 or positions.shape[0] == 0:
        raise ValueError("station_positions_m must have nonempty shape (N, 3).")

    direction = _finite_real_array(propagation_direction, "propagation_direction")
    if direction.shape != (3,):
        raise ValueError("propagation_direction must have shape (3,).")
    # hypot avoids overflow when diagnosing even a wildly invalid direction.
    with np.errstate(over="ignore"):
        direction_norm = float(np.hypot.reduce(direction))
    if not np.isclose(direction_norm, 1.0, rtol=0.0, atol=UNIT_VECTOR_ATOL):
        raise ValueError("propagation_direction must have unit length.")
    if direction[2] >= 0.0:
        raise ValueError("propagation_direction must point strictly downward (z < 0).")

    core = _finite_real_array(core_position_m, "core_position_m")
    if core.shape != (3,):
        raise ValueError("core_position_m must have shape (3,).")
    core_time = _finite_real_scalar(core_time_ns, "core_time_ns")
    curvature = _finite_real_scalar(curvature_ns_per_m2, "curvature_ns_per_m2")
    if curvature < 0.0:
        raise ValueError("curvature_ns_per_m2 must be nonnegative.")

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            offsets = positions - core
            longitudinal_m = offsets @ direction
            predicted_times = core_time + longitudinal_m / C_M_PER_NS
            if curvature > 0.0:
                # Projection avoids cancellation in |d|^2 - (d dot u)^2.
                transverse_m = offsets - longitudinal_m[:, None] * direction
                transverse_squared_m2 = np.sum(transverse_m * transverse_m, axis=1)
                predicted_times = predicted_times + curvature * transverse_squared_m2
    except FloatingPointError as error:
        raise ValueError("Timing calculation exceeds finite float64 arithmetic.") from error

    if not np.all(np.isfinite(predicted_times)):
        raise ValueError("Timing calculation produced non-finite values.")
    return predicted_times
