"""Reference-conditioned diagnostics, deliberately outside the blind fitter.

Fixing a published direction makes this an explanatory check, not reconstruction
validation. Core and direction are both supplied. No chi-square significance is
inferred: curvature is bounded and real-event model errors remain possible.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from auger_reco.physics.plane_front import C_M_PER_NS


def finite_array(value: ArrayLike, name: str) -> NDArray[np.float64]:
    """Copy real finite numerical input, rejecting silent coercions."""
    try:
        if any(isinstance(item, (bool, np.bool_)) for item in np.asarray(value, dtype=object).flat):
            raise ValueError(f"{name} must not contain Boolean values.")
        original = np.asarray(value)
        if original.dtype.kind not in "iuf":
            raise ValueError(f"{name} must be real non-Boolean numeric data.")
        with np.errstate(over="raise", invalid="raise"):
            result = np.array(original, dtype=np.float64, copy=True)
    except (TypeError, OverflowError, FloatingPointError) as error:
        raise ValueError(f"{name} exceeds finite real arithmetic.") from error
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite.")
    return result


def readonly(value: ArrayLike) -> NDArray[np.float64]:
    result = np.array(value, dtype=float, copy=True)
    result.setflags(write=False)
    return result


def geometry_terms(positions, core, direction):
    """Return along-axis distance and squared transverse distance in metres."""
    positions = finite_array(positions, "positions")
    core = finite_array(core, "core")
    direction = finite_array(direction, "direction")
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
        raise ValueError("positions must have nonempty shape (N, 3).")
    if core.shape != (3,) or direction.shape != (3,):
        raise ValueError("core and direction must have shape (3,).")
    if not np.isclose(np.hypot.reduce(direction), 1.0, rtol=0, atol=1e-12):
        raise ValueError("direction must be unit length.")
    if direction[2] >= 0:
        raise ValueError("direction must point strictly downward.")
    try:
        with np.errstate(over="raise", invalid="raise"):
            offsets = positions - core
            along = offsets @ direction
            transverse = offsets - along[:, None] * direction
            rho2 = np.sum(transverse**2, axis=1)
    except FloatingPointError as error:
        raise ValueError("Geometry exceeds finite arithmetic.") from error
    return along, rho2


@dataclass(frozen=True, slots=True)
class FixedDirectionFit:
    """Two nuisance parameters at fixed supplied direction/core; N-2 is nominal."""

    core_position_m: NDArray[np.float64]
    propagation_direction: NDArray[np.float64]
    time_origin_ns: float
    centered_core_time_ns: float
    delay_at_1km_ns: float
    predicted_times_ns: NDArray[np.float64]
    residuals_ns: NDArray[np.float64]
    standardized_residuals: NDArray[np.float64]
    chi_square: float
    objective_sum_squares: float
    nominal_degrees_of_freedom: int
    reduced_chi_square: float
    rms_residual_ns: float
    curvature_at_boundary: bool
    design_condition_number: float
    weighting: str

    def predict_times_ns(self, positions_m: ArrayLike) -> NDArray[np.float64]:
        along, rho2 = geometry_terms(positions_m, self.core_position_m, self.propagation_direction)
        with np.errstate(over="raise", invalid="raise"):
            return self.time_origin_ns + (
                self.centered_core_time_ns + along / C_M_PER_NS + self.delay_at_1km_ns * rho2 / 1e6
            )


def fit_fixed_direction_quadratic(
    positions_m: ArrayLike,
    times_ns: ArrayLike,
    uncertainties_ns: ArrayLike,
    core_position_m: ArrayLike,
    propagation_direction: ArrayLike,
    *,
    weighting: str = "timing",
) -> FixedDirectionFit:
    """Profile time and nonnegative curvature at a specified fixed direction.

    Weighted centered regression yields the unconstrained slope. If negative,
    the exact constrained solution is the zero-curvature boundary, with time
    refitted. This is convex in these two nuisance parameters only. Centered
    epochs avoid loss of finite-difference time derivatives at large timestamps.
    """
    along, rho2 = geometry_terms(positions_m, core_position_m, propagation_direction)
    times = finite_array(times_ns, "times")
    sigma = finite_array(uncertainties_ns, "uncertainties")
    n = len(along)
    if n < 3 or times.shape != (n,) or sigma.shape != (n,):
        raise ValueError("Need at least three stations and aligned (N,) times/sigmas.")
    if np.any(sigma <= 0) or weighting not in ("timing", "uniform"):
        raise ValueError("Need positive uncertainties and timing/uniform weighting.")
    scales = sigma if weighting == "timing" else np.ones(n)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            # Scale weights by a common factor; the optimum is unchanged.
            weights = (scales.min() / scales) ** 2
            weights /= weights.sum()
            x = rho2 / 1e6
            epoch = float(times[0])
            y = (times - epoch) - along / C_M_PER_NS
            xbar = float(weights @ x)
            ybar = float(weights @ y)
            xc = x - xbar
            denominator = float(weights @ (xc**2))
            if denominator <= np.finfo(float).eps * max(1.0, float(weights @ x**2)):
                raise ValueError("Station radii do not identify time and curvature separately.")
            delay = max(0.0, float(weights @ (xc * (y - ybar))) / denominator)
            intercept = ybar - delay * xbar
            residual = y - (intercept + delay * x)
            chi = float(np.sum((residual / sigma) ** 2))
            objective = float(np.sum((residual / scales) ** 2))
            prediction = epoch + (intercept + along / C_M_PER_NS + delay * x)
            design = np.column_stack((np.ones(n), x)) * np.sqrt(weights[:, None])
            normalized = design / np.linalg.norm(design, axis=0)
            condition = float(np.linalg.cond(normalized))
    except FloatingPointError as error:
        raise ValueError("Timing regression exceeds finite arithmetic.") from error
    return FixedDirectionFit(
        readonly(core_position_m),
        readonly(propagation_direction),
        epoch,
        intercept,
        delay,
        readonly(prediction),
        readonly(residual),
        readonly(residual / sigma),
        chi,
        objective,
        n - 2,
        chi / (n - 2),
        float(np.sqrt(np.mean(residual**2))),
        delay == 0.0,
        condition,
        weighting,
    )


def spherical_front_times_ns(
    positions_m: ArrayLike,
    propagation_direction: ArrayLike,
    core_position_m: ArrayLike,
    core_time_ns: float,
    radius_m: float,
) -> NDArray[np.float64]:
    """Exact expanding spherical front, a geometry toy rather than detector MC.

    Centre = core - R*u; arrival at core occurs at core_time. Rationalization
    evaluates (sqrt((R+l)^2+rho^2)-R)/c without subtracting two large radii.
    Unlike the quadratic generator, longitudinal distance changes local curvature.
    """
    along, rho2 = geometry_terms(positions_m, core_position_m, propagation_direction)
    radius = finite_array(radius_m, "radius")
    time = finite_array(core_time_ns, "core_time")
    if radius.ndim != 0 or time.ndim != 0 or radius <= 0:
        raise ValueError("Need a positive scalar radius and finite scalar core time.")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            distance = np.hypot(float(radius) + along, np.sqrt(rho2))
            difference = (2 * float(radius) * along + along**2 + rho2) / (distance + float(radius))
            return float(time) + difference / C_M_PER_NS
    except FloatingPointError as error:
        raise ValueError("Spherical timing exceeds finite arithmetic.") from error
