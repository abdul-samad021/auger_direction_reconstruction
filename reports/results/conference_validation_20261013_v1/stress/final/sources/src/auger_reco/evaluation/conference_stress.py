"""Frozen synthetic model/uncertainty mismatch study for the conference release.

The independent scalar generator is intentionally not detector-realistic. It
separates the mean front, actual random scatter and reported fitting uncertainty.
Run with one BLAS thread; sources, settings, inputs and failures are archived.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from auger_reco.physics import curved_front, plane_front

type FloatArray = NDArray[np.float64]

SEED = 20261013
TRIALS = 100
BOOTSTRAPS = 2000
LAYOUTS = ("well_spread", "elongated", "one_sided")
COUNTS = (7, 13)
DIRECTIONS = ((25.0, 20.0), (55.0, 210.0))
REGIMES = (
    "calibrated_gaussian",
    "asymmetric_mean",
    "radial_calibrated",
    "radial_underreported",
    "heavy_tail_t5",
    "centered_skew",
)
METHODS = ("plane_timing", "plane_uniform", "quadratic_timing", "quadratic_uniform")
CONTRASTS = (
    ("curvature_timing", "plane_timing", "quadratic_timing"),
    ("curvature_uniform", "plane_uniform", "quadratic_uniform"),
    ("weighting_plane", "plane_uniform", "plane_timing"),
    ("weighting_quadratic", "quadratic_uniform", "quadratic_timing"),
)
CORE_M = np.array([120.0, -80.0, 0.0])
REFERENCE_C = 0.299792458
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


@dataclass(frozen=True)
class Scenario:
    """A prescribed geometry/direction/noise setting, not a physical event."""

    base_index: int
    layout: str
    station_count: int
    zenith_deg: float
    azimuth_deg: float
    regime: str

    @property
    def identifier(self) -> str:
        return f"g{self.base_index:02d}_{self.regime}"


def scenarios() -> tuple[Scenario, ...]:
    """Return the prespecified ordering used by keyed random streams."""
    cases = []
    index = 0
    for layout in LAYOUTS:
        for count in COUNTS:
            for theta, phi in DIRECTIONS:
                cases.extend(Scenario(index, layout, count, theta, phi, name) for name in REGIMES)
                index += 1
    return tuple(cases)


def station_positions(layout: str, station_count: int) -> FloatArray:
    """Construct deterministic noncollinear toy stations; never read real data."""
    if layout not in LAYOUTS or station_count not in COUNTS:
        raise ValueError("Unknown prespecified geometry.")
    index = np.arange(13)
    angle = index * np.pi * (3.0 - np.sqrt(5.0))
    radius = 250.0 + 145.0 * index
    positions = np.column_stack(
        (radius * np.cos(angle), radius * np.sin(angle), 12.0 * np.sin(1.7 * index))
    )
    if station_count == 7:
        positions = positions[::2].copy()
    if layout == "elongated":
        positions[:, :2] *= [1.8, 0.25]
    elif layout == "one_sided":
        positions[:, :2] *= 0.7
        positions[:, 0] += 2100.0
    return positions


def independent_mean(
    positions: FloatArray,
    zenith_deg: float,
    azimuth_deg: float,
    *,
    core: FloatArray = CORE_M,
    curvature_delay_ns: float = 80.0,
    asymmetry_delay_ns: float = 0.0,
    origin_time_ns: float = 100000.0,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Generate means with scalar dot products, independently of fitter code.

    The asymmetric term is B*rho*(d.e_theta)/1e6, a smooth directional
    perturbation away from the core. It alters the deterministic mean, whereas
    the separately generated zero-mean fluctuations alter random measurements.
    """
    theta, phi = np.deg2rad([zenith_deg, azimuth_deg])
    sky = np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])
    e_theta = np.array([np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)])
    ux, uy, uz = -sky
    means, radii = [], []
    for x, y, z in np.asarray(positions) - core:
        longitudinal = x * ux + y * uy + z * uz
        rho2 = max(0.0, x * x + y * y + z * z - longitudinal * longitudinal)
        rho = np.sqrt(rho2)
        transverse_coordinate = x * e_theta[0] + y * e_theta[1] + z * e_theta[2]
        means.append(
            origin_time_ns
            + longitudinal / REFERENCE_C
            + curvature_delay_ns * rho2 / 1e6
            + asymmetry_delay_ns * rho * transverse_coordinate / 1e6
        )
        radii.append(rho)
    return sky, np.asarray(means), np.asarray(radii)


def uncertainty_arrays(regime: str, radii_m: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Return actual standard deviation and reported dt as distinct copies."""
    if regime not in REGIMES:
        raise ValueError("Unknown noise regime.")
    sigma = 8.0 + 2.0 * (np.arange(len(radii_m)) % 5)
    radius_km = radii_m / 1000.0
    if regime.startswith("radial_"):
        signal_proxy = (1.0 + (radii_m / 700.0) ** 2) ** -1.5
        sigma = np.sqrt(8.0**2 + (12.0 * radius_km**2) ** 2 + 8.0**2 / signal_proxy)
    reported = sigma.copy()
    if regime == "radial_underreported":
        reported /= 1.0 + 0.8 * radius_km**1.5
    return sigma, reported


def standardized_noise(regime: str, rng: np.random.Generator, shape: tuple[int, ...]) -> FloatArray:
    """Every distribution has population mean zero and variance one."""
    if regime not in REGIMES:
        raise ValueError("Unknown noise regime.")
    if regime == "heavy_tail_t5":
        return np.sqrt(3.0 / 5.0) * rng.standard_t(5.0, size=shape)
    if regime == "centered_skew":
        return rng.exponential(1.0, size=shape) - 1.0
    return rng.normal(size=shape)


def generated_case(case: Scenario, trials: int) -> dict[str, FloatArray]:
    """Generate reproducible paired observations; Gaussian cases share draws."""
    if isinstance(trials, bool) or not isinstance(trials, Integral) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    positions = station_positions(case.layout, case.station_count)
    sky, mean, radius = independent_mean(
        positions,
        case.zenith_deg,
        case.azimuth_deg,
        asymmetry_delay_ns=30.0 if case.regime == "asymmetric_mean" else 0.0,
    )
    actual, reported = uncertainty_arrays(case.regime, radius)
    stream = {"heavy_tail_t5": 1, "centered_skew": 2}.get(case.regime, 0)
    rng = np.random.default_rng(np.random.SeedSequence([SEED, case.base_index, stream]))
    noise = standardized_noise(case.regime, rng, (trials, case.station_count))
    return {
        "positions_m": positions,
        "truth_sky": sky,
        "mean_times_ns": mean,
        "radius_m": radius,
        "actual_sigma_ns": actual,
        "reported_dt_ns": reported,
        "standardized_noise": noise,
        "observed_times_ns": mean + actual * noise,
        "core_m": CORE_M.copy(),
    }


def true_angle_deg(first: FloatArray, second: FloatArray) -> float:
    """Stable independent angle, preserving resolution for exact-fit controls."""
    a, b = first / np.linalg.norm(first), second / np.linalg.norm(second)
    return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(a, b)), a @ b)))


def fit_one(method: str, data: dict[str, FloatArray], observed: FloatArray) -> dict[str, Any]:
    """Retain numerical failures; independently verify every successful result."""
    if method not in METHODS:
        raise ValueError("Unknown method.")
    model, weighting = method.split("_")
    try:
        args = (data["positions_m"], observed, data["reported_dt_ns"])
        if model == "plane":
            fit = plane_front.fit_plane_front(*args, weighting=weighting)
        else:
            fit = curved_front.fit_quadratic_front(
                *args, core_position_m=data["core_m"], weighting=weighting
            )
    except FAILURES as error:
        return {
            "method": method,
            "success": False,
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "attempts": [asdict(attempt) for attempt in getattr(error, "attempts", ())],
        }
    observed_residual = observed - fit.predicted_times_ns
    if not np.allclose(observed_residual, fit.residuals_ns, rtol=0.0, atol=1e-7):
        raise AssertionError("Independent residual audit failed.")
    if not np.isclose(np.linalg.norm(fit.sky_direction), 1.0, rtol=0.0, atol=1e-12):
        raise AssertionError("Nonunit fitted direction.")
    if fit.sky_direction[2] <= 0.0 or not np.allclose(
        fit.sky_direction, -fit.propagation_direction, rtol=0.0, atol=1e-14
    ):
        raise AssertionError("Direction convention audit failed.")
    independent_chi = float(np.sum((observed_residual / data["reported_dt_ns"]) ** 2))
    if not np.isclose(independent_chi, fit.chi_square, rtol=1e-6, atol=1e-12):
        raise AssertionError("Independent chi-square audit failed.")
    return {
        "method": method,
        "success": True,
        "angular_error_deg": true_angle_deg(fit.sky_direction, data["truth_sky"]),
        "nominal_reduced_chi_square": fit.reduced_chi_square,
        "rms_residual_ns": fit.rms_residual_ns,
        "objective_sum_squares": fit.objective_sum_squares,
        "curvature_delay_ns": getattr(fit, "delay_at_1km_ns", None),
        "sky_direction": fit.sky_direction.tolist(),
        "quality_flags": list(fit.quality_flags),
        "optimizer_status": fit.optimizer_status,
        "optimizer_optimality": fit.optimizer_optimality,
        "optimizer_function_evaluations": fit.optimizer_function_evaluations,
        "optimizer_parameters": list(fit.optimizer_parameters),
        "attempts": [asdict(attempt) for attempt in fit.optimizer_attempts],
        "maximum_residual_audit_difference_ns": float(
            np.max(np.abs(observed_residual - fit.residuals_ns))
        ),
    }


def audit_nested(rows: list[dict[str, Any]]) -> int:
    """Quadratic contains the plane; check matched objectives, not reduced chi2."""
    count = 0
    by_method = {row["method"]: row for row in rows}
    for weighting in ("timing", "uniform"):
        plane = by_method[f"plane_{weighting}"]
        curved = by_method[f"quadratic_{weighting}"]
        if plane["success"] and curved["success"]:
            reference = plane["objective_sum_squares"]
            if curved["objective_sum_squares"] > reference + 1e-5 + 1e-6 * reference:
                raise AssertionError("Nested objective audit failed.")
            count += 1
    return count


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> None:
    """Atomically replace only this study's own generated artifact."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(value), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def bootstrap_median(
    values: FloatArray, seed: int, samples: int = BOOTSTRAPS
) -> tuple[float, float]:
    """Paired-trial MC uncertainty, not a detector-population confidence band."""
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Bootstrap requires nonempty finite paired values.")
    rng = np.random.default_rng(np.random.SeedSequence([SEED, 981, seed]))
    draws = rng.integers(0, len(values), size=(samples, len(values)))
    lo, hi = np.quantile(np.median(values[draws], axis=1), [0.025, 0.975])
    return float(lo), float(hi)


def summarize(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize conditional successes and retain denominators for every contrast."""
    summary, contrasts = [], []
    for scenario_index, (identifier, group) in enumerate(records.groupby("scenario", sort=True)):
        metadata = {name: group.iloc[0][name] for name in asdict(scenarios()[0])}
        for method in METHODS:
            subset = group[group.method == method]
            valid = subset[subset.success]
            row = dict(metadata, scenario=identifier, method=method)
            row.update(
                requested=len(subset), successful=len(valid), failed=len(subset) - len(valid)
            )
            for metric in (
                "median_error_deg",
                "p68_error_deg",
                "p95_error_deg",
                "mean_nominal_reduced_chi_square",
                "median_nominal_reduced_chi_square",
                "median_rms_residual_ns",
            ):
                row[metric] = np.nan
            if len(valid):
                row.update(
                    median_error_deg=valid.angular_error_deg.median(),
                    p68_error_deg=valid.angular_error_deg.quantile(0.68),
                    p95_error_deg=valid.angular_error_deg.quantile(0.95),
                    mean_nominal_reduced_chi_square=valid.nominal_reduced_chi_square.mean(),
                    median_nominal_reduced_chi_square=valid.nominal_reduced_chi_square.median(),
                    median_rms_residual_ns=valid.rms_residual_ns.median(),
                )
            summary.append(row)
        for contrast_index, (name, first, second) in enumerate(CONTRASTS):
            a = group[(group.method == first) & group.success].set_index("trial")
            b = group[(group.method == second) & group.success].set_index("trial")
            paired = a.index.intersection(b.index)
            row = dict(metadata, scenario=identifier, contrast=name)
            row.update(
                requested_pairs=len(group[group.method == first]),
                paired_successes=len(paired),
                unpaired_due_to_failure=len(group[group.method == first]) - len(paired),
                median_paired_improvement_deg=np.nan,
                bootstrap95_low_deg=np.nan,
                bootstrap95_high_deg=np.nan,
                fraction_improved_beyond_tolerance=np.nan,
                improvement_tolerance_deg=1e-5,
            )
            if len(paired):
                improvement = (
                    a.loc[paired, "angular_error_deg"] - b.loc[paired, "angular_error_deg"]
                ).to_numpy()
                lo, hi = bootstrap_median(improvement, scenario_index * 10 + contrast_index)
                row.update(
                    median_paired_improvement_deg=np.median(improvement),
                    bootstrap95_low_deg=lo,
                    bootstrap95_high_deg=hi,
                    fraction_improved_beyond_tolerance=np.mean(improvement > 1e-5),
                )
            contrasts.append(row)
    return pd.DataFrame(summary), pd.DataFrame(contrasts)


def exact_controls() -> list[dict[str, Any]]:
    """Run zero-noise matching and deliberate mismatching controls on every base."""
    rows = []
    for case in scenarios()[:: len(REGIMES)]:
        data = generated_case(case, 1)
        for delay in (0.0, 80.0):
            _, exact, _ = independent_mean(
                data["positions_m"], case.zenith_deg, case.azimuth_deg, curvature_delay_ns=delay
            )
            for method in METHODS:
                result = fit_one(method, data, exact)
                matching = method.startswith("quadratic") or delay == 0.0
                if matching and (
                    not result["success"]
                    or result["angular_error_deg"] >= 1e-5
                    or result["rms_residual_ns"] >= 1e-4
                ):
                    raise AssertionError(
                        f"Exact matching control failed: {case.identifier}/{method}"
                    )
                rows.append(
                    dict(result, base_index=case.base_index, delay_ns=delay, matching=matching)
                )
    return rows


def configuration(root: Path, trials: int) -> dict[str, Any]:
    """Fingerprint scientific settings and all directly imported project sources."""
    paths = [
        Path(__file__).resolve(),
        Path(plane_front.__file__).resolve(),
        Path(curved_front.__file__).resolve(),
        root / "docs/conference_stress_protocol.md",
        root / "tests/test_conference_stress.py",
    ]
    if any(not path.is_relative_to(root) for path in paths):
        raise RuntimeError("Imports came from a different repository.")
    return {
        "seed": SEED,
        "trials_per_scenario": trials,
        "bootstrap_resamples": BOOTSTRAPS,
        "scenarios": [asdict(case) for case in scenarios()],
        "expected_datasets": len(scenarios()) * trials,
        "expected_fits": len(scenarios()) * trials * len(METHODS),
        "expected_control_fits": 96,
        "core_position_m": CORE_M.tolist(),
        "curvature_delay_ns": 80.0,
        "asymmetry_delay_ns": 30.0,
        "plane_options": asdict(plane_front.PlaneFrontFitOptions()),
        "quadratic_options": asdict(curved_front.QuadraticFrontFitOptions()),
        "packages": {name: version(name) for name in ("numpy", "scipy", "pandas", "matplotlib")},
        "python": platform.python_version(),
        "sources": {str(path.relative_to(root)): file_digest(path) for path in paths},
        "threads": {
            key: os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")
        },
        "real_events_accessed": 0,
    }


def make_figures(output: Path, summary: pd.DataFrame, contrasts: pd.DataFrame) -> None:
    """Use actual per-scenario data, with no fabricated particle-shower visuals."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [
        "Gaussian\ncalibrated",
        "Asymmetric\nmean",
        "Radial sigma\ncalibrated",
        "Radial sigma\nunderreported",
        "Heavy-tail\nt(5)",
        "Centered\nskew",
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for method, color, label in (
        ("plane_timing", "#55718f", "Plane, timing-weighted"),
        ("quadratic_timing", "#db8336", "Known-core quadratic, timing-weighted"),
    ):
        selected = summary[summary.method == method]
        central = selected.groupby("regime").median_error_deg.median().reindex(REGIMES)
        axes[0].plot(range(len(REGIMES)), central, "o-", color=color, label=label)
        for x, regime in enumerate(REGIMES):
            values = selected[selected.regime == regime].median_error_deg.to_numpy()
            axes[0].scatter(np.full(len(values), x), values, color=color, alpha=0.25, s=20)
    selected = contrasts[contrasts.contrast == "weighting_quadratic"]
    for x, regime in enumerate(REGIMES):
        part = selected[selected.regime == regime].sort_values("base_index")
        offsets = np.linspace(-0.22, 0.22, len(part))
        axes[1].scatter(x + offsets, part.median_paired_improvement_deg, s=28, color="#167d8d")
    axes[1].axhline(0.0, color="black", lw=1)
    axes[0].set_ylabel("True angular error (deg), scenario medians")
    axes[1].set_ylabel("Median paired improvement from weighting (deg)")
    axes[0].set_title("Lines: median across 12 fixed scenarios; dots: each scenario")
    axes[1].set_title("Known-core quadratic: positive favors timing weighting")
    for ax in axes:
        ax.set_xticks(range(len(REGIMES)), labels, fontsize=8)
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    fig.suptitle("Controlled stress tests — not an Auger detector simulation")
    fig.savefig(output / "stress_comparison.png", dpi=180)
    fig.savefig(output / "stress_comparison.svg")
    plt.close(fig)


def run(root: Path, output: Path, trials: int = TRIALS) -> dict[str, Any]:
    """Freeze provenance, resume verified cases and preserve all numerical outcomes."""
    root, output = root.resolve(), output.resolve()
    if isinstance(trials, bool) or not isinstance(trials, Integral) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    config = configuration(root, trials)
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / "configuration.json"
    if config_path.exists():
        if json.loads(config_path.read_text()) != _json_safe(config):
            raise RuntimeError("Configuration or sources changed; cannot resume this run.")
    else:
        if any(output.iterdir()):
            raise RuntimeError("Refusing nonempty output directory without provenance.")
        write_json(config_path, config)
        for relative in config["sources"]:
            target = output / "sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, target)
        write_json(output / "started.json", {"utc": datetime.now(UTC).isoformat()})
    controls_path = output / "exact_controls.json"
    if controls_path.exists():
        controls = json.loads(controls_path.read_text())
    else:
        controls = exact_controls()
        write_json(controls_path, controls)
    records, nested_checks = [], 0
    start = time.monotonic()
    for case_index, case in enumerate(scenarios()):
        case_path = output / f"{case.identifier}.json"
        if case_path.exists():
            payload = json.loads(case_path.read_text())
            data_path = output / f"{case.identifier}.npz"
            if file_digest(data_path) != payload["input_sha256"]:
                raise RuntimeError("Archived generated observations changed.")
        else:
            data = generated_case(case, trials)
            data_path = output / f"{case.identifier}.npz"
            temporary = data_path.with_suffix(".npz.tmp")
            with temporary.open("wb") as stream:
                np.savez_compressed(stream, **data)
            temporary.replace(data_path)
            case_rows, checks = [], 0
            for trial, observed in enumerate(data["observed_times_ns"]):
                fitted = [fit_one(method, data, observed) for method in METHODS]
                checks += audit_nested(fitted)
                case_rows.extend(dict(row, trial=trial) for row in fitted)
            payload = {
                "scenario": asdict(case),
                "input_sha256": file_digest(data_path),
                "nested_objective_checks": checks,
                "fits": case_rows,
            }
            write_json(case_path, payload)
        expected_keys = {(trial, method) for trial in range(trials) for method in METHODS}
        actual_keys = {(row["trial"], row["method"]) for row in payload["fits"]}
        if (
            payload["scenario"] != asdict(case)
            or len(payload["fits"]) != trials * len(METHODS)
            or actual_keys != expected_keys
        ):
            raise RuntimeError("Incomplete or mismatched scenario receipt.")
        nested_checks += payload["nested_objective_checks"]
        records.extend(
            dict(row, scenario=case.identifier, **asdict(case)) for row in payload["fits"]
        )
        print(
            f"Stress cases {case_index + 1}/72 complete; elapsed {time.monotonic() - start:.1f}s",
            flush=True,
        )
    frame = pd.DataFrame(records)
    summary, contrasts = summarize(frame)
    summary.to_csv(output / "scenario_summary.csv", index=False)
    contrasts.to_csv(output / "paired_contrasts.csv", index=False)
    make_figures(output, summary, contrasts)
    report = {
        "requested_fits": len(frame),
        "successful_fits": int(frame.success.sum()),
        "failed_fits": int((~frame.success).sum()),
        "control_fits": len(controls),
        "exact_matching_controls": sum(row["matching"] for row in controls),
        "nested_objective_checks": nested_checks,
        "nested_violations": 0,
        "regime_median_of_scenario_medians": [],
        "completed_utc": datetime.now(UTC).isoformat(),
    }
    for regime in REGIMES:
        for method in METHODS:
            part = summary[(summary.regime == regime) & (summary.method == method)]
            angular = part.median_error_deg.dropna()
            nominal = part.mean_nominal_reduced_chi_square.dropna()
            report["regime_median_of_scenario_medians"].append(
                {
                    "regime": regime,
                    "method": method,
                    "median_error_deg": float(angular.median()) if len(angular) else None,
                    "median_scenario_mean_nominal_chi2": (
                        float(nominal.median()) if len(nominal) else None
                    ),
                }
            )
    if configuration(root, trials) != config:
        raise RuntimeError("Source/configuration changed during execution.")
    write_json(output / "summary.json", report)
    write_json(
        output / "artifact_hashes.json",
        {
            str(path.relative_to(output)): file_digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.name != "artifact_hashes.json"
        },
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=TRIALS)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.output, args.trials), indent=2))


if __name__ == "__main__":
    main()
