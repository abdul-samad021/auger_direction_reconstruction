"""Render equal-event paired comparisons without hiding large-error tails.

The primary frozen report is unchanged. These additional log-scale figures show
its same saved metrics more legibly when a few unstable fits stretch linear axes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot(run_dir: Path) -> None:
    directory = run_dir / "report"
    frame = pd.read_csv(directory / "training_event_metrics.csv", dtype={"event_id": str})
    metrics = (
        ("reduced_chi_square", "In-sample timing agreement", r"Nominal $\chi^2/\nu$"),
        ("heldout_rms_ns", "Conditional station holdout", "Held-out timing RMS [ns]"),
        (
            "separation_from_auger_deg",
            "Published-direction agreement",
            "Separation from Auger [deg]",
        ),
    )
    plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "svg.fonttype": "none"})
    for weighting in ("timing", "uniform"):
        data = frame[frame["weighting"] == weighting]
        fig, axes = plt.subplots(1, 3, figsize=(14, 6.4))
        fig.subplots_adjust(left=0.06, right=0.99, bottom=0.28, top=0.78, wspace=0.30)
        for axis, (metric, title, units) in zip(axes, metrics, strict=True):
            pairs = data.pivot(index="event_id", columns="model", values=metric).dropna()
            values = pairs[["plane", "quadratic"]].to_numpy()
            if not np.isfinite(values).all() or (values <= 0).any():
                raise ValueError("Log-scale figure requires finite positive paired metrics")
            minimum, maximum = float(values.min()) / 1.5, float(values.max()) * 1.5
            axis.plot([minimum, maximum], [minimum, maximum], "--", color="#667085", lw=1.2)
            axis.scatter(
                pairs["plane"],
                pairs["quadratic"],
                s=14,
                alpha=0.6,
                color="#167d9a",
                linewidths=0,
                rasterized=True,
            )
            improved = int((pairs["quadratic"] < pairs["plane"]).sum())
            axis.set(
                xscale="log",
                yscale="log",
                xlim=(minimum, maximum),
                ylim=(minimum, maximum),
                xlabel=f"Plane: {units}",
                ylabel=f"Core-assisted quadratic: {units}",
                title=f"{title}\n{improved}/{len(pairs)} pairs lower with quadratic",
            )
            axis.grid(which="major", alpha=0.15)
            axis.text(
                0.04,
                0.97,
                "Below dashed line: quadratic lower",
                transform=axis.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                color="#344054",
            )
        label = "Timing-weighted" if weighting == "timing" else "Uniform-weighted"
        fig.text(
            0.06,
            0.94,
            "Plane versus curved-front reconstruction on real Auger training events",
            fontsize=17,
            weight="bold",
            color="#142d4e",
        )
        fig.text(
            0.06,
            0.87,
            f"{label} fits • {frame['event_id'].nunique()} training events • "
            "one point per complete event/model pair",
            fontsize=12,
        )
        fig.text(
            0.06,
            0.055,
            "All eligible pairs shown; logarithmic axes retain extreme tails. "
            "Holdout requires all station folds to succeed for both models.\n"
            "Official core and station selection are reused. Auger direction is a "
            "reference, not ground truth. Training analysis is not independent validation.",
            fontsize=10,
            linespacing=1.5,
            color="#344054",
        )
        for suffix in ("png", "svg"):
            path = directory / f"training_pairs_{weighting}_log_v2.{suffix}"
            if path.exists():
                raise FileExistsError(path)
            fig.savefig(path, dpi=180, facecolor="white")
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    plot(parser.parse_args().run_dir.resolve())
