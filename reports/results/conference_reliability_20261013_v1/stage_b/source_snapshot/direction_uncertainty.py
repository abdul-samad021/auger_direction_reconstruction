"""Conditional local direction regions and a frozen known-truth coverage study.

These are local Gaussian approximations, not detector-calibrated error bars.
The core is held fixed. Full-model SVD marginalizes time and curvature rather
than incorrectly treating either fitted nuisance parameter as known. Residual
chi-square is never used to inflate or shrink the supplied timing uncertainty.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from auger_reco.physics import curved_front, plane_front

type FloatArray = NDArray[np.float64]

SEED = 202610131701
TRIALS = 200
LIGHT_SPEED_M_PER_NS = 0.299792458
CORE_M = np.array([120.0, -80.0, 0.0])
CURVATURE_NS = 200.0
LAYOUTS = ("well_spread", "elongated", "ring_anchor", "ring_no_anchor")
DIRECTIONS = ((25.0, 20.0), (55.0, 210.0))
REGIMES = ("calibrated_gaussian", "asymmetric_mean", "underreported_sigma")
PROBABILITIES = (0.68, 0.95)
FAILURES = (
    plane_front.DegenerateStationGeometryError,
    plane_front.PlaneFrontInitializationError,
    plane_front.PlaneFrontOptimizationError,
    curved_front.QuadraticFrontGeometryError,
    curved_front.QuadraticFrontOptimizationError,
    ValueError,
    FloatingPointError,
    OverflowError,
    np.linalg.LinAlgError,
)


@dataclass(frozen=True, slots=True)
class DirectionUncertainty:
    """A local tangent covariance, including applicability warnings.

    Availability means the algebra succeeded, not that frequentist coverage is
    calibrated. In particular, a curvature boundary or another solution branch
    invalidates an unqualified Gaussian interpretation. Radii are tangent-plane
    ellipse semiaxes converted from radians, not an isotropic confidence cone.
    """

    available: bool
    reason: str
    covariance_rad2: FloatArray | None
    tangent_basis: FloatArray
    major_radius_68_deg: float | None
    major_radius_95_deg: float | None
    minor_radius_95_deg: float | None
    normalized_condition_number: float | None
    rank: int
    quality_flags: tuple[str, ...]


def _real_finite(value: ArrayLike, name: str) -> FloatArray:
    original = np.asarray(value)
    if original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numeric values.")
    result = np.array(original, dtype=np.float64, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite.")
    return result


def tangent_basis(sky_direction: ArrayLike) -> FloatArray:
    """Return a deterministic orthonormal 3x2 tangent basis at a unit sky vector."""
    sky = _real_finite(sky_direction, "sky_direction")
    if sky.shape != (3,) or not np.isclose(np.linalg.norm(sky), 1.0, rtol=0, atol=1e-10):
        raise ValueError("sky_direction must be a three-component unit vector.")
    axis = np.eye(3)[int(np.argmin(np.abs(sky)))]
    first = np.cross(axis, sky)
    first /= np.linalg.norm(first)
    basis = np.column_stack((first, np.cross(sky, first)))
    basis.setflags(write=False)
    return basis


def whitened_tangent_jacobian(
    station_positions_m: ArrayLike,
    timing_uncertainties_ns: ArrayLike,
    core_position_m: ArrayLike,
    sky_direction: ArrayLike,
    delay_at_1km_ns: float,
) -> tuple[FloatArray, FloatArray]:
    """Differentiate (tc, two local sky angles, A) independently of fitter code.

    With u=-s, l=d.u and rho²=|d|²-l², the direction derivative is
    (1/c-2*A*l/10^6)*(-d.B), where columns of B are tangent unit vectors.
    Whitening divides each complete row by its reported timing sigma.
    """
    positions = _real_finite(station_positions_m, "station_positions_m")
    sigma = _real_finite(timing_uncertainties_ns, "timing_uncertainties_ns")
    core = _real_finite(core_position_m, "core_position_m")
    sky = _real_finite(sky_direction, "sky_direction")
    delay = _real_finite(delay_at_1km_ns, "delay_at_1km_ns")
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) < 4:
        raise ValueError("station_positions_m must have shape (N,3), N>=4.")
    if sigma.shape != (len(positions),) or np.any(sigma <= 0):
        raise ValueError("Timing uncertainties must have shape (N,) and be positive.")
    if core.shape != (3,) or delay.ndim != 0 or delay < 0:
        raise ValueError("The core must have shape (3,) and curvature be nonnegative.")
    basis = tangent_basis(sky)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        offsets = positions - core
        longitudinal = offsets @ (-sky)
        transverse = np.cross(offsets, sky)
        radial = np.sum(transverse**2, axis=1) / 1e6
        derivative = (1 / LIGHT_SPEED_M_PER_NS - 2 * float(delay) * longitudinal / 1e6)[:, None] * (
            -offsets @ basis
        )
        jacobian = np.column_stack((np.ones(len(positions)), derivative, radial)) / sigma[:, None]
    if not np.isfinite(jacobian).all():
        raise ValueError("The timing Jacobian is not finite.")
    return jacobian, basis


def directional_uncertainty(
    station_positions_m: ArrayLike,
    timing_uncertainties_ns: ArrayLike,
    core_position_m: ArrayLike,
    sky_direction: ArrayLike,
    delay_at_1km_ns: float,
    *,
    relative_rank_tolerance: float = 1e-10,
    boundary_tolerance_ns: float = 1e-6,
) -> DirectionUncertainty:
    """Compute full-model SVD covariance and extract its 2x2 direction block.

    Do not pass the fit residual RMS as sigma. Known/assumed measurement scales
    determine information; a low residual sum cannot repair model mismatch.
    """
    if not np.isfinite(relative_rank_tolerance) or not 0 < relative_rank_tolerance < 1:
        raise ValueError("relative_rank_tolerance must lie strictly between zero and one.")
    if not np.isfinite(boundary_tolerance_ns) or boundary_tolerance_ns <= 0:
        raise ValueError("boundary_tolerance_ns must be finite and positive.")
    jacobian, basis = whitened_tangent_jacobian(
        station_positions_m,
        timing_uncertainties_ns,
        core_position_m,
        sky_direction,
        delay_at_1km_ns,
    )
    flags = []
    if delay_at_1km_ns <= boundary_tolerance_ns:
        flags.append("curvature_boundary")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scales = np.linalg.norm(jacobian, axis=0)
    except FloatingPointError:
        return DirectionUncertainty(
            False,
            "jacobian_scaling_failure",
            None,
            basis,
            None,
            None,
            None,
            None,
            0,
            tuple(flags),
        )
    if not np.isfinite(scales).all() or np.any(scales <= 0):
        return DirectionUncertainty(
            False,
            "zero_or_nonfinite_jacobian_column",
            None,
            basis,
            None,
            None,
            None,
            None,
            0,
            tuple(flags),
        )
    try:
        _, singular, right = np.linalg.svd(jacobian / scales, full_matrices=False)
    except np.linalg.LinAlgError:
        return DirectionUncertainty(
            False,
            "jacobian_svd_failure",
            None,
            basis,
            None,
            None,
            None,
            None,
            0,
            tuple(flags),
        )
    rank = int(np.count_nonzero(singular > relative_rank_tolerance * singular[0]))
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else None
    if rank != 4:
        return DirectionUncertainty(
            False,
            "rank_deficient_full_model",
            None,
            basis,
            None,
            None,
            None,
            condition,
            rank,
            tuple(flags),
        )
    # Every right-singular direction contributes: time/curvature are not fixed.
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            angular_factor = (right.T[1:3] / scales[1:3, None]) / singular[None, :]
            covariance = angular_factor @ angular_factor.T
            if not np.isfinite(covariance).all():
                raise FloatingPointError("Nonfinite local covariance.")
            eigenvalues = np.linalg.eigvalsh(covariance)
            if eigenvalues[0] <= 0:
                raise FloatingPointError("Nonpositive local covariance.")
            major68 = float(np.rad2deg(np.sqrt(-2 * np.log(1 - 0.68) * eigenvalues[-1])))
            major95 = float(np.rad2deg(np.sqrt(-2 * np.log(1 - 0.95) * eigenvalues[-1])))
            minor95 = float(np.rad2deg(np.sqrt(-2 * np.log(1 - 0.95) * eigenvalues[0])))
            if not np.isfinite([major68, major95, minor95]).all():
                raise FloatingPointError("Nonfinite local ellipse radius.")
    except (FloatingPointError, np.linalg.LinAlgError):
        return DirectionUncertainty(
            False,
            "nonpositive_or_nonfinite_covariance",
            None,
            basis,
            None,
            None,
            None,
            condition,
            rank,
            tuple(flags),
        )
    if major95 > 10:
        flags.append("broad_local_region_over_10_deg")
    covariance.setflags(write=False)
    return DirectionUncertainty(
        True,
        "available_local_approximation",
        covariance,
        basis,
        major68,
        major95,
        minor95,
        condition,
        rank,
        tuple(flags),
    )


def log_map_components(
    fitted_sky: ArrayLike,
    true_sky: ArrayLike,
    basis: ArrayLike,
) -> FloatArray:
    """Shortest spherical displacement to truth in the fitted tangent basis."""
    fitted = _real_finite(fitted_sky, "fitted_sky")
    truth = _real_finite(true_sky, "true_sky")
    tangent_basis(fitted)
    tangent_basis(truth)
    axes = _real_finite(basis, "basis")
    if axes.shape != (3, 2) or not np.allclose(axes.T @ axes, np.eye(2), atol=1e-10):
        raise ValueError("basis must have two orthonormal columns.")
    if not np.allclose(axes.T @ fitted, 0.0, atol=1e-10):
        raise ValueError("basis must be tangent at the fitted vector.")
    sine = float(np.linalg.norm(np.cross(fitted, truth)))
    cosine = float(np.clip(fitted @ truth, -1, 1))
    angle = float(np.arctan2(sine, cosine))
    if sine < 1e-14:
        if cosine < 0:
            raise ValueError("The spherical log map is undefined at the antipode.")
        return axes.T @ truth
    return (angle / sine) * (axes.T @ truth)


def squared_direction_distance(
    result: DirectionUncertainty,
    fitted_sky: ArrayLike,
    true_sky: ArrayLike,
) -> float:
    """Mahalanobis distance for a local ellipse; no explicit matrix inverse."""
    if not result.available or result.covariance_rad2 is None:
        raise ValueError("Direction covariance is unavailable.")
    displacement = log_map_components(fitted_sky, true_sky, result.tangent_basis)
    factor = np.linalg.cholesky(result.covariance_rad2)
    standardized = np.linalg.solve(factor, displacement)
    return float(standardized @ standardized)


def wilson_interval(successes: int, total: int) -> tuple[float | None, float | None]:
    """Two-sided 95% Wilson Monte Carlo interval; no detector generalization."""
    if isinstance(successes, bool) or isinstance(total, bool):
        raise ValueError("Counts must be integers.")
    if int(total) != total or int(successes) != successes or not 0 <= successes <= total:
        raise ValueError("Counts must be nonnegative integers with successes<=total.")
    if total == 0:
        return None, None
    z = 1.959963984540054
    fraction = successes / total
    denominator = 1 + z * z / total
    center = (fraction + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(fraction * (1 - fraction) / total + z * z / (4 * total**2))
    return max(0.0, float(center - radius / denominator)), min(
        1.0, float(center + radius / denominator)
    )


def station_layout(name: str) -> tuple[FloatArray, FloatArray]:
    """Prespecified synthetic coordinates; never load a measured Auger event."""
    if name not in LAYOUTS:
        raise ValueError("Unknown layout.")
    if name.startswith("ring"):
        angle = np.deg2rad([0, 50, 115, 185, 235, 300])
        radius = np.array([1390, 1420, 1360, 1440, 1380, 1410])
        points = np.column_stack(
            (radius * np.cos(angle), radius * np.sin(angle), [5, -4, 3, 8, -6, 2])
        )
        sigma = np.array([20, 24, 19, 22, 25, 21], dtype=float)
        if name == "ring_anchor":
            points = np.vstack((points, [130, -80, 1]))
            sigma = np.append(sigma, 3.5)
    else:
        index = np.arange(13)
        angle = index * np.pi * (3 - np.sqrt(5))
        radius = 250 + 145 * index
        points = np.column_stack(
            (radius * np.cos(angle), radius * np.sin(angle), 12 * np.sin(1.7 * index))
        )
        sigma = 8.0 + 2 * (index % 5)
        if name == "elongated":
            points = points[::2].copy()
            points[:, :2] *= [1.8, 0.25]
            sigma = sigma[::2]
    return points + CORE_M, sigma


def independent_mean(
    positions: FloatArray,
    theta_deg: float,
    phi_deg: float,
    asymmetric: bool,
) -> tuple[FloatArray, FloatArray]:
    """Scalar independent simulator with optional controlled mean misspecification."""
    theta, phi = np.deg2rad([theta_deg, phi_deg])
    sky = np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])
    tangent = np.array([np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)])
    means = []
    for x, y, z in positions - CORE_M:
        longitudinal = -x * sky[0] - y * sky[1] - z * sky[2]
        rho2 = max(0.0, x * x + y * y + z * z - longitudinal * longitudinal)
        asymmetry = 30 * np.sqrt(rho2) * (x * tangent[0] + y * tangent[1] + z * tangent[2])
        means.append(
            100000
            + longitudinal / LIGHT_SPEED_M_PER_NS
            + CURVATURE_NS * rho2 / 1e6
            + (asymmetry / 1e6 if asymmetric else 0)
        )
    return sky, np.asarray(means)


def _json(path: Path, content: object) -> None:
    path.write_text(json.dumps(content, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _summarize(records: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    for scenario, frame in records.groupby("scenario", sort=False):
        available = frame["covariance_available"]
        interior = available & ~frame["curvature_boundary"]
        row = {name: frame.iloc[0][name] for name in ("layout", "zenith_deg", "regime")}
        row.update(
            scenario=scenario,
            trials=len(frame),
            fits_successful=int(frame.fit_success.sum()),
            available=int(available.sum()),
            interior_available=int(interior.sum()),
            boundary_count=int(frame.curvature_boundary.sum()),
            median_angular_error_deg=float(frame.angular_error_deg.median()),
            p95_angular_error_deg=float(frame.angular_error_deg.quantile(0.95)),
            mean_nominal_reduced_chi_square=float(frame.reduced_chi_square.mean()),
            median_major_radius_95_deg=float(frame.major_radius_95_deg.median()),
        )
        for probability in PROBABILITIES:
            level = int(probability * 100)
            covered = frame[f"covered_{level}"]
            for label, mask in (
                ("all", pd.Series(True, index=frame.index)),
                ("available", available),
                ("interior", interior),
            ):
                count = int(mask.sum())
                successes = int((covered & mask).sum())
                lower, upper = wilson_interval(successes, count)
                row[f"coverage_{level}_{label}"] = successes / count if count else None
                row[f"coverage_{level}_{label}_low"] = lower
                row[f"coverage_{level}_{label}_high"] = upper
        summaries.append(row)
    return pd.DataFrame(summaries)


def _figures(summary: pd.DataFrame, output: Path, trials: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), layout="constrained")
    colors = {
        "calibrated_gaussian": "#0072B2",
        "asymmetric_mean": "#D55E00",
        "underreported_sigma": "#009E73",
    }
    labels = [
        f"{layout.replace('_', ' ')} / {theta:.0f}°"
        for layout in LAYOUTS
        for theta, _ in DIRECTIONS
    ]
    for panel, probability in zip(axes, PROBABILITIES, strict=True):
        level = int(probability * 100)
        for offset, regime in enumerate(REGIMES):
            selected = summary.loc[summary.regime == regime]
            y = np.arange(len(selected)) + (offset - 1) * 0.2
            value = selected[f"coverage_{level}_all"].to_numpy()
            errors = np.vstack(
                (
                    value - selected[f"coverage_{level}_all_low"],
                    selected[f"coverage_{level}_all_high"] - value,
                )
            )
            panel.errorbar(
                value,
                y,
                xerr=errors,
                fmt="o",
                capsize=2,
                color=colors[regime],
                label=regime.replace("_", " "),
            )
        panel.axvline(probability, color="black", linestyle="--", linewidth=1)
        panel.set(
            xlim=(-0.03, 1.03),
            yticks=np.arange(8),
            yticklabels=labels,
            xlabel="Delivered-and-covered fraction (95% Monte Carlo interval)",
            title=f"Nominal {level}% local direction region",
        )
        panel.invert_yaxis()
        panel.grid(axis="x", alpha=0.2)
    axes[1].legend(loc="lower left", fontsize=8)
    fig.suptitle(
        f"Conditional fixed-core direction uncertainty: {trials} trials per scenario\n"
        "All attempts retained; local Gaussian approximation, no chi-square rescaling"
    )
    for extension in ("png", "svg"):
        fig.savefig(output / f"direction_coverage.{extension}", dpi=180)
    plt.close(fig)


def run_study(output: Path, trials: int = TRIALS, *, smoke: bool = False) -> None:
    """Freeze configuration/source before running; refuse to overwrite any run."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials <= 0:
        raise ValueError("trials must be a positive integer.")
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    source_paths = (
        Path(__file__).resolve(),
        Path(curved_front.__file__).resolve(),
        Path(plane_front.__file__).resolve(),
        root / "docs/direction_uncertainty_protocol.md",
    )
    source_hashes = {}
    for source in source_paths:
        relative = source.relative_to(root)
        snapshot = output / "source_snapshot" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, snapshot)
        source_hashes[str(relative)] = sha256(snapshot.read_bytes()).hexdigest()
    config = {
        "seed": SEED,
        "trials_per_scenario": trials,
        "smoke": smoke,
        "layouts": LAYOUTS,
        "directions_deg": DIRECTIONS,
        "regimes": REGIMES,
        "core_m": CORE_M.tolist(),
        "curvature_delay_at_1km_ns": CURVATURE_NS,
        "options": asdict(curved_front.QuadraticFrontFitOptions()),
        "python": platform.python_version(),
        "libraries": {name: version(name) for name in ("numpy", "scipy", "pandas")},
        "started_utc": datetime.now(UTC).isoformat(),
        "sources": source_hashes,
    }
    _json(output / "protocol_lock.json", config)
    start = time.monotonic()
    records = []
    attempt_path = output / "optimizer_attempts.jsonl"
    with attempt_path.open("x", encoding="utf-8") as attempt_stream:
        for layout_index, layout in enumerate(LAYOUTS):
            positions, actual_sigma = station_layout(layout)
            for direction_index, (theta, phi) in enumerate(DIRECTIONS):
                for regime in REGIMES:
                    scenario = f"{layout}_t{theta:g}_{regime}"
                    sky, mean = independent_mean(positions, theta, phi, regime == "asymmetric_mean")
                    reported = actual_sigma / 2 if regime == "underreported_sigma" else actual_sigma
                    times = np.empty((trials, len(positions)))
                    for trial in range(trials):
                        # Same noise for three regimes; keyed by layout, direction, trial.
                        rng = np.random.default_rng(
                            np.random.SeedSequence([SEED, layout_index, direction_index, trial])
                        )
                        times[trial] = mean + actual_sigma * rng.standard_normal(len(positions))
                    np.savez_compressed(
                        output / f"inputs_{scenario}.npz",
                        positions_m=positions,
                        core_m=CORE_M,
                        actual_sigma_ns=actual_sigma,
                        reported_sigma_ns=reported,
                        mean_times_ns=mean,
                        observed_times_ns=times,
                        true_sky=sky,
                    )
                    for trial, observed in enumerate(times):
                        row = {
                            "scenario": scenario,
                            "trial": trial,
                            "layout": layout,
                            "zenith_deg": theta,
                            "azimuth_deg": phi,
                            "regime": regime,
                            "fit_success": False,
                            "covariance_available": False,
                            "curvature_boundary": False,
                            "covered_68": False,
                            "covered_95": False,
                            "exception_type": "",
                            "exception": "",
                            "angular_error_deg": None,
                            "reduced_chi_square": None,
                            "major_radius_95_deg": None,
                        }
                        attempts = ()
                        try:
                            fit = curved_front.fit_quadratic_front(
                                positions,
                                observed,
                                reported,
                                core_position_m=CORE_M,
                                weighting="timing",
                            )
                            attempts = fit.optimizer_attempts
                            row["fit_success"] = True
                            uncertainty = directional_uncertainty(
                                positions, reported, CORE_M, fit.sky_direction, fit.delay_at_1km_ns
                            )
                            row.update(
                                covariance_available=uncertainty.available,
                                covariance_reason=uncertainty.reason,
                                covariance_flags=";".join(uncertainty.quality_flags),
                                fit_quality_flags=";".join(fit.quality_flags),
                                curvature_boundary="curvature_boundary"
                                in uncertainty.quality_flags,
                                delay_at_1km_ns=fit.delay_at_1km_ns,
                                fitted_core_time_ns=fit.core_time_ns,
                                fitted_sky_x=fit.sky_direction[0],
                                fitted_sky_y=fit.sky_direction[1],
                                fitted_sky_z=fit.sky_direction[2],
                                angular_error_deg=plane_front.angular_separation_deg(
                                    fit.sky_direction, sky
                                ),
                                reduced_chi_square=fit.reduced_chi_square,
                                major_radius_95_deg=uncertainty.major_radius_95_deg,
                                major_radius_68_deg=uncertainty.major_radius_68_deg,
                                minor_radius_95_deg=uncertainty.minor_radius_95_deg,
                                normalized_condition=uncertainty.normalized_condition_number,
                                jacobian_rank=uncertainty.rank,
                            )
                            if uncertainty.available:
                                distance = squared_direction_distance(
                                    uncertainty, fit.sky_direction, sky
                                )
                                row["mahalanobis_squared"] = distance
                                for i, j in ((0, 0), (0, 1), (1, 1)):
                                    row[f"covariance_{i}{j}_rad2"] = uncertainty.covariance_rad2[
                                        i, j
                                    ]
                                for probability in PROBABILITIES:
                                    row[f"covered_{int(probability * 100)}"] = bool(
                                        distance <= -2 * np.log(1 - probability)
                                    )
                        except FAILURES as error:
                            row.update(exception_type=type(error).__name__, exception=str(error))
                            if row["covariance_available"]:
                                row["covariance_available"] = False
                                row["covariance_reason"] = (
                                    "region_evaluation_failure_after_covariance"
                                )
                            if not row["fit_success"]:
                                attempts = getattr(error, "attempts", ())
                        attempt_stream.write(
                            json.dumps(
                                {
                                    "scenario": scenario,
                                    "trial": trial,
                                    "attempts": [asdict(attempt) for attempt in attempts],
                                },
                                allow_nan=False,
                            )
                            + "\n"
                        )
                        records.append(row)
                    print(f"Completed {scenario}: {trials} attempts", flush=True)
    frame = pd.DataFrame(records)
    frame.to_csv(output / "trials.csv", index=False)
    summary = _summarize(frame)
    summary.to_csv(output / "coverage_summary.csv", index=False)
    _figures(summary, output, trials)
    _json(
        output / "run_status.json",
        {
            "elapsed_seconds": time.monotonic() - start,
            "attempted_fits": len(frame),
            "successful_fits": int(frame.fit_success.sum()),
            "covariance_available": int(frame.covariance_available.sum()),
            "boundary_count": int(frame.curvature_boundary.sum()),
            "protocol_lock_sha256": sha256(
                (output / "protocol_lock.json").read_bytes()
            ).hexdigest(),
            "completed_utc": datetime.now(UTC).isoformat(),
        },
    )
    _json(
        output / "manifest.json",
        {
            "files": {
                str(path.relative_to(output)): sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.rglob("*"))
                if path.is_file()
            }
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    run_study(args.output, args.trials, smoke=args.smoke)


if __name__ == "__main__":
    main()
