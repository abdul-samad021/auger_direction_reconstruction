"""Complete Stage A presentation artifacts without rerunning or altering fits.

The frozen experiment finished every trial and saved its tables, then Matplotlib
rejected a tiny negative errorbar width from Wilson endpoint roundoff. This
separate renderer clips only plotted errorbar widths, not statistical values.
It preserves the exact shared uncertainty helper used by the parallel Stage B.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_new_json(path: Path, content: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(content, stream, indent=2, allow_nan=False)
        stream.write("\n")


def complete(output: Path) -> None:
    """Refuse overwrite; verify provenance; render tables; seal all artifacts."""
    output = output.resolve()
    protected = {
        str(path.relative_to(output)): digest(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    generated = [
        "direction_coverage.png",
        "direction_coverage.svg",
        "run_status.json",
        "reporting_recovery.json",
        "manifest.json",
        "reporting_recovery_source.py",
    ]
    if any((output / name).exists() for name in generated):
        raise FileExistsError("A completion artifact already exists; do not overwrite it.")
    lock = json.loads((output / "protocol_lock.json").read_text())
    for path, expected in lock["sources"].items():
        if digest(output / "source_snapshot" / path) != expected:
            raise ValueError(f"Frozen source snapshot changed: {path}")
    frame = pd.read_csv(output / "trials.csv")
    summary = pd.read_csv(output / "coverage_summary.csv")
    expected = (
        len(lock["layouts"])
        * len(lock["directions_deg"])
        * len(lock["regimes"])
        * lock["trials_per_scenario"]
    )
    if len(frame) != expected or int(summary.trials.sum()) != expected:
        raise ValueError("The saved experiment is incomplete.")
    if frame[["scenario", "trial"]].duplicated().any():
        raise ValueError("Duplicate trial identifiers.")
    for scenario, group in frame.groupby("scenario"):
        if set(group.trial) != set(range(lock["trials_per_scenario"])):
            raise ValueError(f"Missing attempted trials in {scenario}.")
    labels = [
        f"{layout.replace('_', ' ')} / {theta:.0f}°"
        for layout in lock["layouts"]
        for theta, _ in lock["directions_deg"]
    ]
    colors = ("#0072B2", "#D55E00", "#009E73")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.3), layout="constrained")
    for panel, probability in zip(axes, (0.68, 0.95), strict=True):
        level = int(probability * 100)
        for offset, (regime, color) in enumerate(zip(lock["regimes"], colors, strict=True)):
            selected = summary.loc[summary.regime == regime]
            value = selected[f"coverage_{level}_all"].to_numpy()
            errors = np.vstack(
                (
                    value - selected[f"coverage_{level}_all_low"],
                    selected[f"coverage_{level}_all_high"] - value,
                )
            )
            if not np.isfinite(errors).all() or np.min(errors) < -1e-12:
                raise ValueError("Error widths are not merely numerical endpoint roundoff.")
            # Presentation-only repair: unchanged statistical table remains authoritative.
            plotted_errors = np.maximum(errors, 0.0)
            panel.errorbar(
                value,
                np.arange(len(selected)) + (offset - 1) * 0.2,
                xerr=plotted_errors,
                fmt="o",
                capsize=2,
                color=color,
                label=regime.replace("_", " "),
            )
        panel.axvline(probability, color="black", linestyle="--", linewidth=1)
        panel.set(
            xlim=(-0.03, 1.03),
            yticks=np.arange(len(labels)),
            yticklabels=labels,
            xlabel="Delivered-and-covered fraction (95% Monte Carlo interval)",
            title=f"Nominal {level}% local direction region",
        )
        panel.invert_yaxis()
        panel.grid(axis="x", alpha=0.2)
    axes[1].legend(loc="lower left", fontsize=8)
    fig.suptitle(
        f"Conditional fixed-core uncertainty: {lock['trials_per_scenario']} trials/scenario\n"
        "All attempts retained; local Gaussian approximation; no chi-square rescaling"
    )
    for extension in ("png", "svg"):
        fig.savefig(output / f"direction_coverage.{extension}", dpi=180)
    plt.close(fig)
    for relative, expected_hash in protected.items():
        if digest(output / relative) != expected_hash:
            raise ValueError(f"An original scientific artifact changed: {relative}")
    with (output / "reporting_recovery_source.py").open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    write_new_json(
        output / "reporting_recovery.json",
        {
            "reason": (
                "All fits complete; original Matplotlib rendering rejected "
                "Wilson endpoint roundoff."
            ),
            "repair": (
                "Plot widths clipped at zero only when >=-1e-12; all original tables unchanged."
            ),
            "no_fitter_rerun": True,
            "no_uncertainty_method_change": True,
            "completed_utc": datetime.now(UTC).isoformat(),
            "original_artifacts_unchanged": protected,
            "renderer_sha256": digest(Path(__file__)),
        },
    )
    write_new_json(
        output / "run_status.json",
        {
            "attempted_fits": len(frame),
            "successful_fits": int(frame.fit_success.sum()),
            "covariance_available": int(frame.covariance_available.sum()),
            "boundary_count": int(frame.curvature_boundary.sum()),
            "fit_runtime_seconds": None,
            "runtime_note": (
                "Original process stopped at plotting before writing a runtime receipt."
            ),
            "protocol_lock_sha256": digest(output / "protocol_lock.json"),
            "completed_utc": datetime.now(UTC).isoformat(),
            "reporting_recovered_without_rerunning_fits": True,
        },
    )
    write_new_json(
        output / "manifest.json",
        {
            "files": {
                str(path.relative_to(output)): digest(path)
                for path in sorted(output.rglob("*"))
                if path.is_file()
            }
        },
    )
    print(json.dumps({"artifacts": len(protected), "trials": len(frame), "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    complete(parser.parse_args().output)
