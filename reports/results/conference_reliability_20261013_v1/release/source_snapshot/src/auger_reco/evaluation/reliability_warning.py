"""Development-locked warning study; true directions are evaluation-only.

This conditional-core synthetic study is independent of Stage A's coverage
outcomes. Its runtime policy sees only a fit-only scalar uncertainty diagnostic.
No real event files are read, and validation observations are created only after
the development-selected policy has been serialized and cryptographically sealed.
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
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from auger_reco.evaluation.direction_uncertainty import directional_uncertainty
from auger_reco.physics import curved_front, plane_front

type FloatArray = NDArray[np.float64]

SEED = 202610132701
TRIALS = 100
ERROR_LIMIT_DEG = 1.0
THRESHOLDS_DEG = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
LAYOUTS = ("spread", "anchored_ring", "anchor_poor_ring")
REGIMES = ("matched", "asymmetric_mean", "underreported_dt")
CORE_M = np.array([0.0, 0.0, 0.0])
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
class Scenario:
    """A fixed synthetic setting, never a measured detector event."""

    split: str
    geometry_index: int
    direction_index: int
    layout: str
    count: int
    zenith_deg: float
    azimuth_deg: float
    regime: str

    @property
    def identifier(self) -> str:
        return f"{self.split}_g{self.geometry_index}_d{self.direction_index}_{self.regime}"


@dataclass(frozen=True, slots=True)
class WarningFeatures:
    """Strict fit-only interface: deliberately no truth/error/reference field."""

    fit_success: bool
    uncertainty_available: bool
    curvature_boundary: bool
    major_radius_95_deg: float | None


@dataclass(frozen=True, slots=True)
class WarningPolicy:
    """Immutable development decision; held-out performance cannot tune it."""

    threshold_deg: float
    development_viable: bool
    selection_reason: str
    development_records_sha256: str
    locked_at_utc: str
    error_limit_deg: float = ERROR_LIMIT_DEG


def warning(features: WarningFeatures, policy: WarningPolicy) -> tuple[bool, str]:
    """Apply the single frozen rule without looking at the actual true error."""
    if not np.isfinite(policy.threshold_deg) or policy.threshold_deg <= 0:
        raise ValueError("The diagnostic threshold must be finite and positive.")
    if not features.fit_success:
        return True, "fit_failure"
    radius = features.major_radius_95_deg
    if not features.uncertainty_available or radius is None or not np.isfinite(radius):
        return True, "uncertainty_unavailable"
    if radius < 0:
        return True, "invalid_uncertainty"
    if features.curvature_boundary:
        return True, "curvature_boundary"
    if radius > policy.threshold_deg:
        return True, "large_local_uncertainty"
    return False, "unflagged"


def scenarios(split: str) -> tuple[Scenario, ...]:
    """Validation changes counts, directions, positions and random streams."""
    if split not in ("development", "validation"):
        raise ValueError("Unknown split.")
    counts = (7, 13) if split == "development" else (8, 14)
    directions = ((25.0, 35.0), (55.0, 210.0))
    if split == "validation":
        directions = ((35.0, 100.0), (50.0, 290.0))
    result = []
    for layout_index, layout in enumerate(LAYOUTS):
        for count_index, count in enumerate(counts):
            geometry_index = 2 * layout_index + count_index
            for direction_index, (zenith, azimuth) in enumerate(directions):
                for regime in REGIMES:
                    result.append(
                        Scenario(
                            split,
                            geometry_index,
                            direction_index,
                            layout,
                            count,
                            zenith,
                            azimuth,
                            regime,
                        )
                    )
    return tuple(result)


def station_positions(case: Scenario) -> FloatArray:
    """Toy arrays include a narrow radial range and an optional central anchor."""
    index = np.arange(case.count)
    if case.layout == "spread":
        angle = index * np.pi * (3.0 - np.sqrt(5.0))
        radius = np.linspace(200.0, 1900.0, case.count)
    elif case.layout in ("anchored_ring", "anchor_poor_ring"):
        angle = np.deg2rad(np.linspace(-48.0, 48.0, case.count))
        radius = 1400.0 + 35.0 * np.sin(2.1 * index)
    else:
        raise ValueError("Unknown layout.")
    positions = np.column_stack(
        (radius * np.cos(angle), radius * np.sin(angle), 5.0 * np.sin(1.3 * index))
    )
    if case.layout == "anchored_ring":
        positions[case.count // 2] = [120.0, -80.0, 2.0]
    if case.split == "validation":
        rotation = np.deg2rad(23.0)
        matrix = np.array(
            [[np.cos(rotation), -np.sin(rotation)], [np.sin(rotation), np.cos(rotation)]]
        )
        positions[:, :2] = positions[:, :2] @ matrix.T
        rng = np.random.default_rng(np.random.SeedSequence([SEED, 90, case.geometry_index]))
        positions += rng.normal(size=positions.shape) * [45.0, 45.0, 3.0]
    return positions


def generate(case: Scenario, trials: int, *, smoke: bool = False) -> dict[str, FloatArray]:
    """Independent scalar timing generator, sharing noise only within each split."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    positions = station_positions(case)
    theta, phi = np.deg2rad([case.zenith_deg, case.azimuth_deg])
    sky = np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])
    e_theta = np.array([np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)])
    means = []
    for x, y, z in positions - CORE_M:
        longitudinal = -(x * sky[0] + y * sky[1] + z * sky[2])
        rho2 = max(0.0, x * x + y * y + z * z - longitudinal * longitudinal)
        asymmetric = 0.0
        if case.regime == "asymmetric_mean":
            asymmetric = (
                80.0 * np.sqrt(rho2) * (x * e_theta[0] + y * e_theta[1] + z * e_theta[2]) / 1e6
            )
        means.append(100000.0 + longitudinal / 0.299792458 + 200.0 * rho2 / 1e6 + asymmetric)
    actual_sigma = 12.0 + 4.0 * (np.arange(case.count) % 5)
    reported_dt = actual_sigma.copy()
    if case.regime == "underreported_dt":
        reported_dt *= 0.5
    split_key = 1 if case.split == "development" else 2
    stream = np.array([SEED, int(smoke), split_key, case.geometry_index, case.direction_index])
    rng = np.random.default_rng(np.random.SeedSequence(stream))
    noise = rng.normal(size=(trials, case.count))
    return {
        "positions_m": positions,
        "core_m": CORE_M.copy(),
        "truth_sky": sky,
        "mean_times_ns": np.asarray(means),
        "actual_sigma_ns": actual_sigma,
        "reported_dt_ns": reported_dt,
        "standardized_noise": noise,
        "observed_times_ns": np.asarray(means) + actual_sigma * noise,
        "seed_sequence": stream,
    }


def true_angle_deg(first: FloatArray, second: FloatArray) -> float:
    """Evaluation-only stable angle; not used for any runtime warning feature."""
    first = first / np.linalg.norm(first)
    second = second / np.linalg.norm(second)
    return float(np.rad2deg(np.arctan2(np.linalg.norm(np.cross(first, second)), first @ second)))


def fit_one(data: dict[str, FloatArray], observed: FloatArray) -> dict[str, Any]:
    """Record complete outcomes, then independently evaluate the truth error."""
    try:
        fit = curved_front.fit_quadratic_front(
            data["positions_m"],
            observed,
            data["reported_dt_ns"],
            core_position_m=data["core_m"],
            weighting="timing",
        )
    except FAILURES as error:
        return {
            "fit_success": False,
            "uncertainty_available": False,
            "curvature_boundary": False,
            "major_radius_95_deg": None,
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "attempts": [asdict(attempt) for attempt in getattr(error, "attempts", ())],
        }
    try:
        uncertainty = directional_uncertainty(
            data["positions_m"],
            data["reported_dt_ns"],
            data["core_m"],
            fit.sky_direction,
            fit.delay_at_1km_ns,
        )
        uncertainty_fields = {
            "uncertainty_available": uncertainty.available,
            "curvature_boundary": "curvature_boundary" in uncertainty.quality_flags,
            "major_radius_95_deg": uncertainty.major_radius_95_deg,
            "uncertainty_reason": uncertainty.reason,
            "uncertainty_flags": list(uncertainty.quality_flags),
            "normalized_condition_number": uncertainty.normalized_condition_number,
        }
    except FAILURES as error:
        # A covariance failure is not an optimizer failure. Preserve the actual
        # fit and error, expose the diagnostic failure, and always warn.
        uncertainty_fields = {
            "uncertainty_available": False,
            "curvature_boundary": fit.delay_at_1km_ns <= 1e-6,
            "major_radius_95_deg": None,
            "uncertainty_reason": f"{type(error).__name__}: {error}",
            "uncertainty_flags": ["uncertainty_calculation_failed"],
            "normalized_condition_number": None,
        }
    independent_chi = float(
        np.sum(((observed - fit.predicted_times_ns) / data["reported_dt_ns"]) ** 2)
    )
    if not np.isclose(independent_chi, fit.chi_square, rtol=1e-7, atol=1e-9):
        raise AssertionError("Independent residual objective audit failed.")
    return {
        "fit_success": True,
        **uncertainty_fields,
        "angular_error_deg": true_angle_deg(fit.sky_direction, data["truth_sky"]),
        "sky_direction": fit.sky_direction.tolist(),
        "delay_at_1km_ns": fit.delay_at_1km_ns,
        "core_time_ns": fit.core_time_ns,
        "nominal_reduced_chi_square": fit.reduced_chi_square,
        "chi_square": fit.chi_square,
        "optimizer_status": fit.optimizer_status,
        "optimizer_optimality": fit.optimizer_optimality,
        "quality_flags": list(fit.quality_flags),
        "attempts": [asdict(attempt) for attempt in fit.optimizer_attempts],
        "failure_type": None,
        "failure_message": None,
    }


def features(row: dict[str, Any]) -> WarningFeatures:
    """Explicitly whitelist only fit-only fields, excluding evaluation columns."""
    return WarningFeatures(
        bool(row["fit_success"]),
        bool(row["uncertainty_available"]),
        bool(row["curvature_boundary"]),
        row["major_radius_95_deg"],
    )


def wilson(successes: int, total: int) -> tuple[float | None, float | None, float | None]:
    """Wilson 95% binomial interval for a fixed-scenario Monte Carlo proportion."""
    if successes < 0 or total < successes:
        raise ValueError("Invalid binomial counts.")
    if total == 0:
        return None, None, None
    z = 1.959963984540054
    fraction = successes / total
    denominator = 1.0 + z * z / total
    center = (fraction + z * z / (2 * total)) / denominator
    width = (
        z * np.sqrt(fraction * (1 - fraction) / total + z * z / (4 * total * total)) / denominator
    )
    return fraction, max(0.0, center - width), min(1.0, center + width)


def evaluate(rows: list[dict[str, Any]], policy: WarningPolicy | None) -> dict[str, Any]:
    """Keep failures separate: they warn, but have no fictitious angular error."""
    successful = [row for row in rows if row["fit_success"]]
    decisions = [warning(features(row), policy)[0] if policy else False for row in successful]
    errors = np.array([row["angular_error_deg"] for row in successful], dtype=float)
    bad = errors > ERROR_LIMIT_DEG
    flagged = np.array(decisions, dtype=bool)
    tp = int(np.sum(bad & flagged))
    fp = int(np.sum(~bad & flagged))
    fn = int(np.sum(bad & ~flagged))
    tn = int(np.sum(~bad & ~flagged))
    failed = len(rows) - len(successful)
    result: dict[str, Any] = {
        "requested": len(rows),
        "fit_successes": len(successful),
        "fit_failures": failed,
        "flagged_successes": int(np.sum(flagged)),
        "failure_warnings": failed,
        "retained": tn + fn,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "large_errors": tp + fn,
        "threshold_deg": policy.threshold_deg if policy else None,
    }
    paired_regime_mixture = len({row.get("regime", "unspecified") for row in rows}) > 1
    result["interval_scope"] = (
        "omitted: pooled regimes share random draws"
        if paired_regime_mixture
        else "approximate Wilson Monte Carlo interval for independent draws"
    )
    proportions = {
        "warning_fraction": (tp + fp + failed, len(rows)),
        "retention_fraction": (tn + fn, len(rows)),
        "sensitivity": (tp, tp + fn),
        "false_warning_rate": (fp, fp + tn),
        "precision": (tp, tp + fp),
        "unflagged_large_error_risk": (fn, tn + fn),
        "all_successful_large_error_risk": (tp + fn, len(successful)),
    }
    for name, (numerator, denominator) in proportions.items():
        proportion, low, high = wilson(numerator, denominator)
        if paired_regime_mixture:
            low, high = None, None
        result.update({name: proportion, name + "_low95": low, name + "_high95": high})
    for prefix, selected in (("all", errors), ("unflagged", errors[~flagged])):
        result[prefix + "_median_error_deg"] = float(np.median(selected)) if len(selected) else None
        result[prefix + "_p95_error_deg"] = (
            float(np.quantile(selected, 0.95)) if len(selected) else None
        )
    return result


def select_policy(
    rows: list[dict[str, Any]],
    records_digest: str,
) -> tuple[WarningPolicy, list[dict[str, Any]]]:
    """Choose once using the declared development criterion, never validation."""
    if not rows or any(row["split"] != "development" for row in rows):
        raise ValueError("Policy selection requires development-only records.")
    candidates = []
    for threshold in THRESHOLDS_DEG:
        policy = WarningPolicy(threshold, False, "candidate", records_digest, "pending")
        assessment = evaluate(rows, policy)
        sensitivity, false_warning = assessment["sensitivity"], assessment["false_warning_rate"]
        assessment["viable"] = (
            sensitivity is not None
            and false_warning is not None
            and sensitivity >= 0.90
            and false_warning <= 0.30
        )
        assessment["balanced_accuracy"] = (
            0.5 * (sensitivity + 1.0 - false_warning)
            if sensitivity is not None and false_warning is not None
            else -1.0
        )
        candidates.append(assessment)
    viable = [candidate for candidate in candidates if candidate["viable"]]
    if viable:
        chosen = max(viable, key=lambda row: (row["retention_fraction"], row["threshold_deg"]))
        reason = "Maximum retention among development sensitivity>=0.90, false-warning<=0.30."
    else:
        chosen = max(candidates, key=lambda row: (row["balanced_accuracy"], row["threshold_deg"]))
        reason = "No viable development candidate; exploratory maximum balanced-accuracy fallback."
    return WarningPolicy(
        chosen["threshold_deg"],
        bool(viable),
        reason,
        records_digest,
        now(),
    ), candidates


def now() -> str:
    return datetime.now(UTC).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    """Create only: new runs must never overwrite frozen scientific outputs."""
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(safe(payload), indent=2, allow_nan=False) + "\n")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_policy(path: Path, expected_sha256: str) -> WarningPolicy:
    """Check the exact locked bytes before use; mutation aborts validation."""
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError("Frozen policy bytes changed; validation must stop.")
    return WarningPolicy(**json.loads(payload))


def run_phase(
    output: Path,
    split: str,
    trials: int,
    locked_policy: tuple[Path, str] | None = None,
) -> list[dict[str, Any]]:
    """Generate/fill a split only at the appropriate development-lock stage."""
    if (split == "validation") != (locked_policy is not None):
        raise ValueError("Validation requires a locked policy; development must not use one.")
    folder = output / split
    folder.mkdir()
    write_json(folder / "generation_started.json", {"started_at_utc": now(), "split": split})
    records = []
    for case in scenarios(split):
        policy = load_policy(*locked_policy) if locked_policy else None
        data = generate(case, trials, smoke=trials != TRIALS)
        np.savez_compressed(folder / (case.identifier + ".npz"), **data)
        case_records = []
        for trial, observed in enumerate(data["observed_times_ns"]):
            row = dict(asdict(case), scenario=case.identifier, trial=trial)
            row.update(fit_one(data, observed))
            if policy:
                row["warning"], row["warning_reason"] = warning(features(row), policy)
            case_records.append(row)
        write_json(folder / (case.identifier + "_records.json"), case_records)
        records.extend(case_records)
        print(f"{case.identifier}: {len(case_records)} attempts", flush=True)
    write_json(folder / "records.json", records)
    flat = [{key: value for key, value in row.items() if key != "attempts"} for row in records]
    pd.DataFrame(flat).to_csv(folder / "records.csv", index=False)
    write_json(
        folder / "generation_completed.json", {"completed_at_utc": now(), "records": len(records)}
    )
    return records


def summarize(rows: list[dict[str, Any]], policy: WarningPolicy) -> pd.DataFrame:
    result = []
    groupings = [("overall", "all", rows)]
    for field in ("regime", "layout", "scenario"):
        for value in sorted({row[field] for row in rows}):
            groupings.append((field, value, [row for row in rows if row[field] == value]))
    for group_type, group, subset in groupings:
        for method, selected_policy in (("frozen_warning", policy), ("no_warning", None)):
            result.append(
                dict(
                    group_type=group_type,
                    group=group,
                    method=method,
                    **evaluate(subset, selected_policy),
                )
            )
    return pd.DataFrame(result)


def plot_results(summary: pd.DataFrame, output: Path, policy: WarningPolicy) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    selected = summary[(summary.group_type == "regime") & (summary.method == "frozen_warning")]
    selected = selected.set_index("group").loc[list(REGIMES)]
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.9), layout="constrained")
    x = np.arange(len(REGIMES))
    labels = ["Matched\nmodel", "Asymmetric\nmean", "Underreported\nuncertainties"]
    for axis, metric, title in zip(
        axes[:2],
        ("sensitivity", "false_warning_rate"),
        ("Large-error detection", "False warnings on errors ≤ 1°"),
        strict=True,
    ):
        values = selected[metric].to_numpy(dtype=float)
        low = selected[metric + "_low95"].to_numpy(dtype=float)
        high = selected[metric + "_high95"].to_numpy(dtype=float)
        axis.errorbar(x, values, yerr=[values - low, high - values], fmt="o", capsize=4)
        axis.set(
            xticks=x,
            xticklabels=labels,
            ylim=(0, 1.03),
            title=title,
            ylabel="Fraction (95% Wilson)",
        )
        axis.grid(alpha=0.2)
    for index, (_, row) in enumerate(selected.iterrows()):
        axes[2].plot(
            [1, row.retention_fraction],
            [row.all_successful_large_error_risk, row.unflagged_large_error_risk],
            "o-",
            label=labels[index].replace("\n", " "),
        )
    axes[2].set(
        xlabel="Fraction retained",
        ylabel="Fraction with true error > 1°",
        xlim=(0, 1.04),
        ylim=(0, 1.04),
        title="Frozen policy vs no-warning baseline",
    )
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.2)
    qualifier = "development-viable" if policy.development_viable else "NOT development-viable"
    fig.suptitle(
        f"Independent synthetic validation: frozen radius threshold {policy.threshold_deg:g}°\n"
        f"({qualifier}; conditional on the supplied exact core)",
        fontsize=12,
    )
    fig.savefig(output / "warning_validation.png", dpi=190)
    fig.savefig(output / "warning_validation.svg")
    plt.close(fig)


def run(output: Path, trials: int = TRIALS) -> dict[str, Any]:
    """Run development, freeze, then independently generate and evaluate validation."""
    if output.exists():
        raise FileExistsError("Use a new output directory; frozen output is immutable.")
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    output.mkdir(parents=True)
    repository = Path(__file__).resolve().parents[3]
    source_paths = (
        Path(__file__).resolve(),
        repository / "src/auger_reco/evaluation/direction_uncertainty.py",
        repository / "src/auger_reco/physics/curved_front.py",
        repository / "src/auger_reco/physics/plane_front.py",
        repository / "docs/reliability_warning_protocol.md",
    )
    source_folder = output / "source_snapshot"
    source_folder.mkdir()
    sources = []
    for source in source_paths:
        destination = source_folder / source.name
        shutil.copy2(source, destination)
        sources.append({"path": str(source.relative_to(repository)), "sha256": digest(source)})
    started = time.perf_counter()
    write_json(
        output / "configuration.json",
        {
            "started_at_utc": now(),
            "seed": SEED,
            "trials_per_scenario": trials,
            "large_error_strictly_above_deg": ERROR_LIMIT_DEG,
            "candidate_thresholds_deg": THRESHOLDS_DEG,
            "sources": sources,
            "python": platform.python_version(),
            "versions": {
                name: version(name) for name in ("numpy", "scipy", "pandas", "matplotlib")
            },
            "development_scenarios": [asdict(case) for case in scenarios("development")],
            "validation_scenarios": [asdict(case) for case in scenarios("validation")],
        },
    )
    development = run_phase(output, "development", trials)
    policy, candidates = select_policy(development, digest(output / "development/records.json"))
    pd.DataFrame(candidates).to_csv(output / "development_candidates.csv", index=False)
    policy_path = output / "locked_policy.json"
    write_json(policy_path, asdict(policy))
    policy_digest = digest(policy_path)
    write_json(
        output / "policy_lock_receipt.json", {"sha256": policy_digest, "sealed_at_utc": now()}
    )
    validation = run_phase(output, "validation", trials, (policy_path, policy_digest))
    load_policy(policy_path, policy_digest)
    for source in sources:
        if digest(repository / source["path"]) != source["sha256"]:
            raise RuntimeError("Source changed during experiment; do not promote this run.")
    development_summary = summarize(development, policy)
    summary = summarize(validation, policy)
    development_summary.to_csv(output / "development_summary.csv", index=False)
    summary.to_csv(output / "validation_summary.csv", index=False)
    plot_results(summary, output, policy)
    result = {
        "completed_at_utc": now(),
        "elapsed_seconds": time.perf_counter() - started,
        "development_attempts": len(development),
        "validation_attempts": len(validation),
        "policy": asdict(policy),
        "policy_sha256": policy_digest,
        "development": evaluate(development, policy),
        "validation": evaluate(validation, policy),
        "validation_no_warning": evaluate(validation, None),
        "interpretation": (
            "Conditional-core toy stress test; not a detector-population safety guarantee."
        ),
    }
    write_json(output / "results.json", result)
    artifacts = [
        {"path": str(path.relative_to(output)), "sha256": digest(path)}
        for path in sorted(output.rglob("*"))
        if path.is_file()
    ]
    write_json(output / "manifest.json", {"created_at_utc": now(), "artifacts": artifacts})
    print(json.dumps(safe(result), indent=2, allow_nan=False), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=TRIALS)
    args = parser.parse_args()
    run(args.output.resolve(), args.trials)


if __name__ == "__main__":
    main()
