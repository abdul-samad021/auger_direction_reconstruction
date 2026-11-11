"""Experimental fixed-shape lateral-signal core estimator, not Auger replication.

The radial form follows Eq. 5.7 of arXiv:2007.09035, but beta/gamma are supplied
uncalibrated study settings. We omit non-triggered-detector likelihoods, signal
asymmetry, saturation recovery and the full detector-response model. A weighted
log-signal objective is a surrogate, not calibrated chi-square. Do not silently
substitute this estimator into production or claim a true directional improvement.
"""

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares


def _finite(value, name):
    if any(isinstance(item, (bool, np.bool_)) for item in np.asarray(value, dtype=object).flat):
        raise ValueError(f"{name} must not contain Boolean values.")
    original = np.asarray(value)
    if original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be real numeric non-Boolean data.")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.array(original, dtype=np.float64, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite.")
    return result


def _readonly(value):
    result = np.array(value, dtype=float, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class SignalCoreFitOptions:
    """Fixed slopes are experimental knobs, not Auger-calibrated coefficients."""

    beta: float
    gamma: float
    radial_softening_m: float = 1.0
    domain_padding_fraction: float = 1.0
    minimum_stations: int = 6
    maximum_function_evaluations: int = 2000
    optimizer_tolerance: float = 1e-10
    condition_warning_threshold: float = 1e6

    def __post_init__(self):
        for name in (
            "beta",
            "gamma",
            "radial_softening_m",
            "domain_padding_fraction",
            "optimizer_tolerance",
            "condition_warning_threshold",
        ):
            value = _finite(getattr(self, name), name)
            if value.ndim != 0:
                raise ValueError(f"{name} must be a scalar.")
        if self.beta >= 0 or self.beta + self.gamma >= 0:
            raise ValueError("This decreasing-shape study requires beta<0 and beta+gamma<0.")
        if self.radial_softening_m <= 0 or self.domain_padding_fraction <= 0:
            raise ValueError("Softening and domain padding must be positive.")
        if not np.finfo(float).eps < self.optimizer_tolerance < 1:
            raise ValueError("Optimizer tolerance must lie between float64 epsilon and 1.")
        if self.condition_warning_threshold <= 1:
            raise ValueError("Condition warning threshold must exceed one.")
        for name, minimum in (("minimum_stations", 4), ("maximum_function_evaluations", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}.")


class SignalCoreOptimizationError(RuntimeError):
    """All seeds failed; diagnostics remain available to an experiment runner."""

    def __init__(self, message, attempts):
        super().__init__(message)
        self.attempts = tuple(attempts)


def _geometry(positions, direction, core):
    positions = _finite(positions, "positions")
    direction = _finite(direction, "direction")
    core = _finite(core, "core")
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
        raise ValueError("positions must have nonempty shape (N,3).")
    if direction.shape != (3,) or core.shape != (3,):
        raise ValueError("direction and core must have shape (3,).")
    if not np.isclose(np.hypot.reduce(direction), 1, rtol=0, atol=1e-12):
        raise ValueError("direction must be unit length.")
    if direction[2] >= -0.01:
        raise ValueError("Signal core experiment excludes near-horizontal directions.")
    return positions, direction, core


def _log_shape(positions, direction, core, options):
    offsets = positions - core
    along = offsets @ direction
    transverse = offsets - along[:, None] * direction
    rho = np.hypot.reduce(transverse, axis=1)
    radius = np.hypot(rho, options.radial_softening_m)
    reference = np.hypot(1000.0, options.radial_softening_m)
    # Softening is explicit and normalized so S(rho=1000m) remains S1000.
    return options.beta * np.log(radius / reference) + (options.beta + options.gamma) * np.log(
        (radius + 700) / (reference + 700)
    )


def predict_signals_vem(
    positions_m: ArrayLike,
    propagation_direction: ArrayLike,
    core_position_m: ArrayLike,
    s1000_vem: float,
    *,
    options: SignalCoreFitOptions,
) -> NDArray[np.float64]:
    """Evaluate the explicitly softened modified-NKG signal profile."""
    if not isinstance(options, SignalCoreFitOptions):
        raise TypeError("options must be SignalCoreFitOptions.")
    positions, direction, core = _geometry(positions_m, propagation_direction, core_position_m)
    size = _finite(s1000_vem, "s1000")
    if size.ndim != 0 or size <= 0:
        raise ValueError("s1000 must be a positive scalar.")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            predicted = np.exp(
                np.log(float(size)) + _log_shape(positions, direction, core, options)
            )
    except FloatingPointError as error:
        raise ValueError("Signal prediction exceeds finite arithmetic.") from error
    if not np.isfinite(predicted).all() or np.any(predicted <= 0):
        raise ValueError("Signal prediction underflowed or is nonfinite.")
    return predicted


@dataclass(frozen=True, slots=True)
class SignalCoreFitResult:
    """Conditional signal estimate; no physical/core confidence interval implied."""

    core_position_m: NDArray[np.float64]
    propagation_direction: NDArray[np.float64]
    s1000_vem: float
    predicted_signals_vem: NDArray[np.float64]
    log_standardized_residuals: NDArray[np.float64]
    objective_sum_squares: float
    final_jacobian_rank: int
    final_jacobian_condition_number: float
    optimizer_attempts: tuple[dict, ...]
    quality_flags: tuple[str, ...]
    options: SignalCoreFitOptions
    bounds_xy_m: NDArray[np.float64]


def fit_signal_core(
    positions_m: ArrayLike,
    signals_vem: ArrayLike,
    signal_uncertainties_vem: ArrayLike,
    *,
    propagation_direction: ArrayLike,
    core_z_m: float,
    options: SignalCoreFitOptions,
) -> SignalCoreFitResult:
    """Fit x/y and profiled log S1000 at fixed direction, z and signal-shape slopes.

    Input signals must already obey a documented detector/saturation selection.
    The caller must not treat sat=2 as an ordinary observation without validating
    its recovery. No official core x/y, direction or shower-plane distances enter.
    Sigma_log=sqrt(log1p((dS/S)^2)) is a fixed observed-error approximation.
    Multiseed solutions and domain boundaries are retained for identifiability
    assessment. The nonlinear search is scaled to kilometres about the array.
    """
    if not isinstance(options, SignalCoreFitOptions):
        raise TypeError("options must be SignalCoreFitOptions.")
    z = _finite(core_z_m, "core_z")
    if z.ndim != 0:
        raise ValueError("core_z must be scalar.")
    positions, direction, _ = _geometry(positions_m, propagation_direction, [0.0, 0.0, float(z)])
    signals = _finite(signals_vem, "signals")
    errors = _finite(signal_uncertainties_vem, "signal_uncertainties")
    n = len(positions)
    if n < options.minimum_stations or signals.shape != (n,) or errors.shape != (n,):
        raise ValueError("Insufficient stations or misaligned signal arrays.")
    if np.any(signals <= 0) or np.any(errors <= 0):
        raise ValueError("Signals and their uncertainties must be strictly positive.")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        # Anchoring first avoids large-origin cancellation and sum overflow.
        anchor = positions[0, :2]
        center = anchor + np.mean(positions[:, :2] - anchor, axis=0)
        local = (positions[:, :2] - center) / 1000
        singular = np.linalg.svd(local - local.mean(axis=0), compute_uv=False)
        if singular[0] == 0 or singular[1] <= 1e-10 * singular[0]:
            raise ValueError("Signal stations must span two horizontal dimensions.")
        span = np.ptp(local, axis=0)
        lower = local.min(axis=0) - options.domain_padding_fraction * span
        upper = local.max(axis=0) + options.domain_padding_fraction * span
        log_observed = np.log(signals)
        sigma_log = np.sqrt(np.log1p((errors / signals) ** 2))
        if np.any(sigma_log <= 0):
            raise ValueError("Signal uncertainties are below numerical resolution.")
        weights = (sigma_log.min() / sigma_log) ** 2
        weights /= weights.sum()

    def state(xy):
        core = np.array([*(center + 1000 * xy), float(z)])
        shape = _log_shape(positions, direction, core, options)
        log_size = float(weights @ (log_observed - shape))
        residual = (log_observed - log_size - shape) / sigma_log
        return core, log_size, residual

    starts = [
        np.zeros(2),
        local[np.argmax(signals)],
        np.average(local, axis=0, weights=signals / signals.max()),
        np.average(local, axis=0, weights=np.sqrt(signals / signals.max())),
        (local.min(axis=0) + local.max(axis=0)) / 2,
    ]
    attempts = []
    successful = []
    for index, seed in enumerate(starts):
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                fit = least_squares(
                    lambda xy: state(xy)[2],
                    seed,
                    bounds=(lower, upper),
                    x_scale="jac",
                    ftol=options.optimizer_tolerance,
                    xtol=options.optimizer_tolerance,
                    gtol=options.optimizer_tolerance,
                    max_nfev=options.maximum_function_evaluations,
                )
            valid = bool(fit.success and np.isfinite(fit.fun).all() and np.isfinite(fit.x).all())
            attempts.append(
                {
                    "seed_index": index,
                    "success": valid,
                    "status": int(fit.status),
                    "message": str(fit.message),
                    "cost": float(fit.cost),
                    "optimality": float(fit.optimality),
                    "nfev": int(fit.nfev),
                    "njev": int(fit.njev) if fit.njev is not None else None,
                    "parameters_xy_km": fit.x.tolist(),
                    "active_mask": fit.active_mask.tolist(),
                }
            )
            if valid:
                successful.append(fit)
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as error:
            attempts.append(
                {
                    "seed_index": index,
                    "success": False,
                    "exception": type(error).__name__,
                    "message": str(error),
                }
            )
    if not successful:
        raise SignalCoreOptimizationError("No signal-core seed converged.", attempts)
    best = min(successful, key=lambda fit: float(np.dot(fit.fun, fit.fun)))
    core, log_size, residual = state(best.x)
    # Profiled x/y derivatives are orthogonal to the normalization derivative;
    # adding the latter restores the full three-parameter local rank diagnostic.
    jacobian = np.column_stack((best.jac, 1 / sigma_log))
    norms = np.linalg.norm(jacobian, axis=0)
    normalized = jacobian / np.where(norms > 0, norms, 1)
    singular = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.sum(singular > singular[0] * 1e-10))
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else float("inf")
    flags = [
        "experimental_fixed_shape",
        "conditional_direction_and_core_z",
        "no_nontriggered_likelihood",
        "uncalibrated_log_signal_objective",
    ]
    if rank < 3:
        flags.append("rank_deficient")
    if condition > options.condition_warning_threshold:
        flags.append("ill_conditioned")
    if np.any(best.active_mask):
        flags.append("core_domain_boundary")
    if any(
        np.linalg.norm(fit.x - best.x) > 0.1 and fit.cost <= best.cost + 1 for fit in successful
    ):
        flags.append("multiple_near_equal_core_solutions")
    with np.errstate(over="raise", invalid="raise"):
        size = float(np.exp(log_size))
    prediction = predict_signals_vem(positions, direction, core, size, options=options)
    return SignalCoreFitResult(
        _readonly(core),
        _readonly(direction),
        size,
        _readonly(prediction),
        _readonly(residual),
        float(residual @ residual),
        rank,
        condition,
        tuple(attempts),
        tuple(flags),
        options,
        _readonly(center + 1000 * np.stack((lower, upper))),
    )
