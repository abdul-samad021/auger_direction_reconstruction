"""Paired, descriptive synthesis of the already-observed training population.

This module never loads detector JSON or opens validation/test events. Bootstrap
intervals describe resampling of the selected training events, not truth accuracy
or unbiased generalization. Real-data angles are agreement with Auger's reference.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

SEED = 2026101309
RESAMPLES = 2000
METRICS = {
    "reduced_chi_square": ("Nominal reduced chi-square", "dimensionless", False),
    "rms_residual_ns": ("In-sample timing RMS", "ns", False),
    "separation_from_auger_deg": ("Separation from Auger reference", "deg", False),
    "heldout_rms_ns": ("Conditional held-out timing RMS", "ns", True),
    "heldout_normalized_mse": ("Conditional held-out normalized MSE", "dimensionless", True),
    "maximum_loo_direction_shift_deg": ("Maximum conditional LOO direction shift", "deg", True),
}
GROUPS = (
    "all_training",
    "previous_development",
    "remaining_training",
    "multiplicity_6",
    "multiplicity_7_9",
    "multiplicity_10_19",
    "multiplicity_20_plus",
)


def _boolean(value: str) -> bool:
    if value not in {"True", "False"}:
        raise ValueError(f"Invalid boolean value: {value!r}")
    return value == "True"


def read_metrics(path: Path) -> dict[tuple[str, str, str], dict]:
    """Reject ambiguous identities and nonfinite values, retain missing metrics."""
    return read_metric_bytes(path.read_bytes())


def read_metric_bytes(data: bytes) -> dict[tuple[str, str, str], dict]:
    """Parse the same immutable bytes that are hashed and archived by the runner."""
    records = {}
    with io.StringIO(data.decode("utf-8"), newline="") as stream:
        for source in csv.DictReader(stream):
            row = dict(source)
            event_id = row["event_id"]
            if not event_id.isdigit() or len(event_id) != 12:
                raise ValueError("Expected a twelve-digit event identity.")
            if row["model"] not in {"plane", "quadratic"}:
                raise ValueError("Unexpected model.")
            if row["weighting"] not in {"timing", "uniform"}:
                raise ValueError("Unexpected weighting.")
            key = event_id, row["model"], row["weighting"]
            if key in records:
                raise ValueError(f"Duplicate event/model/weighting: {key}")
            for name in (
                "previous_development",
                "full_success",
                "heldout_complete",
                "influence_complete",
            ):
                row[name] = _boolean(row[name])
            row["number_of_stations"] = int(row["number_of_stations"])
            if row["number_of_stations"] < 1:
                raise ValueError("Station count must be positive.")
            for name in METRICS:
                value = None if row[name] == "" else float(row[name])
                if value is not None and (not np.isfinite(value) or value < 0):
                    raise ValueError(f"Invalid nonnegative finite metric {name}: {value}")
                row[name] = value
            records[key] = row
    if not records:
        raise ValueError("No event records.")
    for event_id in {key[0] for key in records}:
        rows = [
            records.get((event_id, model, weight))
            for model in ("plane", "quadratic")
            for weight in ("timing", "uniform")
        ]
        if any(row is None for row in rows):
            raise ValueError(f"Incomplete model matrix for {event_id}")
        for field in ("number_of_stations", "previous_development"):
            if len({row[field] for row in rows}) != 1:
                raise ValueError(f"Inconsistent {field} for {event_id}")
    return records


def group_contains(row: dict, group: str) -> bool:
    """Apply fixed, outcome-independent multiplicity/development groupings."""
    n = row["number_of_stations"]
    predicates = {
        "all_training": True,
        "previous_development": row["previous_development"],
        "remaining_training": not row["previous_development"],
        "multiplicity_6": n == 6,
        "multiplicity_7_9": 7 <= n <= 9,
        "multiplicity_10_19": 10 <= n <= 19,
        "multiplicity_20_plus": n >= 20,
    }
    return predicates[group]


def paired_summary(plane, quadratic, *, resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    """Summarize paired differences, retaining all adverse outcomes and exact ties."""
    first = np.asarray(plane, dtype=float)
    second = np.asarray(quadratic, dtype=float)
    if first.ndim != 1 or first.shape != second.shape or not first.size:
        raise ValueError("Paired arrays must have equal nonempty one-dimensional shapes.")
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        raise ValueError("Paired arrays must be finite.")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 2:
        raise ValueError("At least two bootstrap resamples are required.")
    difference = second - first
    interval = None
    if first.size >= 2:
        rng = np.random.default_rng(seed)
        draws = np.empty(resamples)
        # Bound temporary memory independently of cohort size and resample count.
        for start in range(0, resamples, 128):
            stop = min(resamples, start + 128)
            indices = rng.integers(0, first.size, size=(stop - start, first.size))
            draws[start:stop] = np.median(difference[indices], axis=1)
        interval = np.quantile(draws, [0.025, 0.975]).tolist()
    return {
        "n": int(first.size),
        "plane_quantiles_p50_p68_p95": np.quantile(first, [0.5, 0.68, 0.95]).tolist(),
        "quadratic_quantiles_p50_p68_p95": np.quantile(second, [0.5, 0.68, 0.95]).tolist(),
        "median_paired_difference_quadratic_minus_plane": float(np.median(difference)),
        "median_paired_difference_bootstrap_95_interval": interval,
        "quadratic_lower_count": int(np.count_nonzero(difference < 0)),
        "quadratic_higher_count": int(np.count_nonzero(difference > 0)),
        "exact_tie_count": int(np.count_nonzero(difference == 0)),
        "resamples": resamples,
        "seed": seed,
    }


def summarize(records: dict, *, resamples: int = RESAMPLES) -> list[dict]:
    results = []
    event_ids = sorted({key[0] for key in records})
    for weighting in ("timing", "uniform"):
        for group in GROUPS:
            eligible = [
                event_id
                for event_id in event_ids
                if group_contains(records[event_id, "plane", weighting], group)
            ]
            for metric, (label, unit, conditional) in METRICS.items():
                included, excluded, plane, quadratic = [], [], [], []
                for event_id in eligible:
                    rows = [records[event_id, model, weighting] for model in ("plane", "quadratic")]
                    completeness = (
                        "influence_complete"
                        if metric.startswith("maximum_loo")
                        else "heldout_complete"
                    )
                    usable = all(
                        row["full_success"]
                        and row[metric] is not None
                        and (not conditional or row[completeness])
                        for row in rows
                    )
                    if not usable:
                        excluded.append(event_id)
                        continue
                    included.append(event_id)
                    plane.append(rows[0][metric])
                    quadratic.append(rows[1][metric])
                summary = (
                    paired_summary(plane, quadratic, resamples=resamples) if included else None
                )
                results.append(
                    {
                        "weighting": weighting,
                        "group": group,
                        "metric": metric,
                        "label": label,
                        "unit": unit,
                        "conditional": conditional,
                        "eligible_count": len(eligible),
                        "included_event_ids": included,
                        "excluded_event_ids": excluded,
                        "summary": summary,
                    }
                )
    return results


def make_figures(records: dict, results: list[dict], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = ("reduced_chi_square", "heldout_rms_ns", "separation_from_auger_deg")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), layout="constrained")
    for ax, metric in zip(axes, metrics, strict=True):
        item = next(
            r
            for r in results
            if r["weighting"] == "timing" and r["group"] == "all_training" and r["metric"] == metric
        )
        ids = item["included_event_ids"]
        x = np.array([records[i, "plane", "timing"][metric] for i in ids])
        y = np.array([records[i, "quadratic", "timing"][metric] for i in ids])
        if np.any(x <= 0) or np.any(y <= 0):
            raise ValueError("Logarithmic figures require strictly positive values; none omitted.")
        ax.scatter(x, y, s=12, color="#126a87", alpha=0.65)
        limits = min(x.min(), y.min()) * 0.7, max(x.max(), y.max()) * 1.4
        ax.plot(limits, limits, "--", color="#555555", linewidth=1)
        ax.set(
            xscale="log",
            yscale="log",
            xlim=limits,
            ylim=limits,
            xlabel=f"Plane ({item['unit']})",
            ylabel=f"Quadratic ({item['unit']})",
            title=(
                f"{item['label']}\n{len(ids)}/{item['eligible_count']} paired training events"
                + (
                    f"; {len(item['excluded_event_ids'])} unavailable"
                    if item["excluded_event_ids"]
                    else ""
                )
            ),
        )
        ax.grid(alpha=0.16)
    fig.suptitle(
        "Timing-weighted reconstruction: all complete paired outcomes shown\n"
        "Published-core-assisted quadratic model; Auger direction is a reference, not truth"
    )
    for suffix in ("png", "svg"):
        fig.savefig(output / f"training_paired_comparison.{suffix}", dpi=220)
    plt.close(fig)

    groups = (
        "all_training",
        "multiplicity_6",
        "multiplicity_7_9",
        "multiplicity_10_19",
        "multiplicity_20_plus",
    )
    labels = ("All training", "6 stations", "7–9 stations", "10–19 stations", "20+ stations")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), layout="constrained")
    for ax, metric in zip(axes, metrics, strict=True):
        for index, group in enumerate(groups):
            item = next(
                r
                for r in results
                if r["weighting"] == "timing" and r["group"] == group and r["metric"] == metric
            )
            summary = item["summary"]
            if summary is None:
                ax.text(
                    0.03,
                    index,
                    (
                        "No eligible events"
                        if item["eligible_count"] == 0
                        else f"{item['eligible_count']} structurally unavailable pairs"
                    ),
                    transform=ax.get_yaxis_transform(),
                    fontsize=8,
                )
                continue
            value = summary["median_paired_difference_quadratic_minus_plane"]
            interval = summary["median_paired_difference_bootstrap_95_interval"]
            if interval is not None:
                ax.plot(interval, [index, index], color="#126a87", linewidth=2)
            ax.plot(value, index, "o", color="#126a87")
            ax.annotate(
                f"n={summary['n']}",
                (value, index),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )
        ax.axvline(0, color="#555555", linestyle="--", linewidth=1)
        ax.set(
            yticks=range(len(groups)),
            yticklabels=labels,
            ylim=(4.6, -0.65),
            title=METRICS[metric][0],
            xlabel=f"Median paired difference ({METRICS[metric][1]})",
        )
        ax.grid(axis="x", alpha=0.16)
    fig.suptitle(
        "Quadratic minus plane: negative means lower metric\n"
        "95% paired event-bootstrap intervals; descriptive training-sample resampling"
    )
    for suffix in ("png", "svg"):
        fig.savefig(output / f"training_paired_intervals.{suffix}", dpi=220)
    plt.close(fig)


def training_ids(configuration_bytes: bytes) -> set[str]:
    """Verify the baseline configuration envelope before accepting its whitelist."""
    envelope = json.loads(configuration_bytes)
    payload = envelope["payload"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != envelope["sha256"]:
        raise ValueError("Training configuration checksum mismatch.")
    identifiers = payload["training_ids"]
    if (
        not identifiers
        or len(set(identifiers)) != len(identifiers)
        or any(not isinstance(i, str) or not i.isdigit() or len(i) != 12 for i in identifiers)
    ):
        raise ValueError("Training whitelist must contain unique twelve-digit IDs.")
    return set(identifiers)


def run(source: Path, output: Path, *, configuration: Path) -> dict:
    """Write an exclusive new analysis directory, never replace a saved run."""
    if output.exists():
        raise FileExistsError(output)
    source_bytes = source.read_bytes()
    code_bytes = Path(__file__).read_bytes()
    configuration_bytes = configuration.read_bytes()
    records = read_metric_bytes(source_bytes)
    if {key[0] for key in records} != training_ids(configuration_bytes):
        raise ValueError("Metric IDs do not exactly match the authorized training population.")
    results = summarize(records)
    output.mkdir(parents=True, exist_ok=False)
    (output / "input_event_metrics.csv").write_bytes(source_bytes)
    (output / "source_snapshot.py").write_bytes(code_bytes)
    (output / "training_configuration.json").write_bytes(configuration_bytes)
    payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "input_path": str(source.resolve()),
        "input_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_sha256": hashlib.sha256(code_bytes).hexdigest(),
        "training_configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
        "event_count": len({key[0] for key in records}),
        "seed": SEED,
        "resamples": RESAMPLES,
        "interpretation": "Descriptive paired resampling of already-observed training events; "
        "not truth accuracy, not blinded validation, not population inference.",
        "comparisons": results,
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    flat = []
    for row in results:
        summary = row["summary"]
        flat.append(
            {
                "weighting": row["weighting"],
                "group": row["group"],
                "metric": row["metric"],
                "unit": row["unit"],
                "eligible": row["eligible_count"],
                "paired": 0 if summary is None else summary["n"],
                "excluded": len(row["excluded_event_ids"]),
                **({} if summary is None else summary),
            }
        )
    fields = list(dict.fromkeys(key for row in flat for key in row))
    with (output / "paired_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(flat)
    make_figures(records, results, output)
    return {"events": payload["event_count"], "comparisons": len(results), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--training-configuration", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.source, args.output, configuration=args.training_configuration), indent=2
        )
    )


if __name__ == "__main__":
    main()
