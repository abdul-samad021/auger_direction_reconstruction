"""Event-equal reporting from sealed training-pilot checkpoints only.

This module never opens raw events or discovers additional event directories.
Every read is gated by the configured training identifiers and verified envelope
hashes. Full-fit and held-out metrics have separate eligibility denominators.
Station residuals are first summarized within an event, never pooled across
events. Missing or failed folds cannot masquerade as a complete prediction.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from auger_reco.data.development_sample import canonical_event_id
from auger_reco.data.direction_reference import DIRECTION_FRAME_VERSION

MODELS = ("plane", "quadratic")
WEIGHTINGS = ("timing", "uniform")
GROUPS = (
    "all_training",
    "previous_development",
    "remaining_training",
    "multiplicity_6",
    "multiplicity_7_9",
    "multiplicity_10_19",
    "multiplicity_20_plus",
    "multiplicity_under_6",
    "multiplicity_unknown",
)
METRICS = (
    "reduced_chi_square",
    "rms_residual_ns",
    "separation_from_auger_deg",
    "heldout_rms_ns",
    "heldout_normalized_mse",
    "maximum_loo_direction_shift_deg",
)
INFLUENCE_WARNING_DEG = 1.0
LEGACY_DIRECTION_FRAME_VERSION = "legacy-unrotated-core-site-comparison-v0"


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _envelope(path: Path, root: Path) -> tuple[dict, str]:
    """Reject escape paths, incomplete envelopes, and altered payloads."""
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Checkpoint path escapes its run directory: {path}.")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("payload"), dict):
        raise ValueError(f"Invalid checkpoint envelope: {path}.")
    payload = document["payload"]
    digest = _digest(payload)
    if document.get("sha256") != digest:
        raise ValueError(f"Checkpoint integrity mismatch: {path}.")
    return payload, digest


def _number(value: object, *, nonnegative: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Checkpoint metric is not a real number or null.")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError("Checkpoint metric is nonfinite or outside its valid range.")
    return result


def _write_bytes(path: Path, content: bytes) -> None:
    """Replace only a named derived report artifact, after flush and fsync."""
    descriptor, name = tempfile.mkstemp(prefix=".report-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _selected(frame: pd.DataFrame, group: str) -> pd.DataFrame:
    if group == "all_training":
        return frame
    if group == "previous_development":
        return frame[frame["previous_development"]]
    if group == "remaining_training":
        return frame[~frame["previous_development"]]
    counts = pd.to_numeric(frame["number_of_stations"], errors="raise")
    if group == "multiplicity_unknown":
        return frame[counts.isna()]
    if group == "multiplicity_under_6":
        return frame[counts < 6]
    if group == "multiplicity_6":
        return frame[counts == 6]
    if group == "multiplicity_7_9":
        return frame[(counts >= 7) & (counts <= 9)]
    if group == "multiplicity_10_19":
        return frame[(counts >= 10) & (counts <= 19)]
    if group == "multiplicity_20_plus":
        return frame[counts >= 20]
    raise ValueError(f"Unknown report group: {group}.")


def _event_rows(
    event_id: str,
    prediction: dict | None,
    outcome: dict | None,
    previous: bool,
    direction_frame_version: str,
) -> list[dict]:
    """Retain four event/method rows, including entirely absent checkpoints."""
    station_count = None
    records = [] if prediction is None else prediction.get("records", [])
    station_records = [] if prediction is None else prediction.get("station_residuals", [])
    if prediction is not None:
        metadata = prediction.get("event_metadata", {})
        station_count = metadata.get("number_of_stations")
        if (
            isinstance(station_count, bool)
            or not isinstance(station_count, int)
            or station_count < 1
        ):
            raise ValueError(f"Invalid station count in prediction {event_id}.")
    if not isinstance(records, list) or not isinstance(station_records, list):
        raise ValueError("Prediction records and station residuals must be lists.")
    comparisons = (
        {}
        if outcome is None
        else {
            (row["model"], row["weighting"]): row
            for row in outcome.get("reference_comparisons", [])
        }
    )
    if outcome is not None and len(comparisons) != len(outcome.get("reference_comparisons", [])):
        raise ValueError("Duplicate reference comparison.")
    output = []
    for model in MODELS:
        for weighting in WEIGHTINGS:
            matches = [
                r for r in records if r.get("model") == model and r.get("weighting") == weighting
            ]
            full = [r for r in matches if r.get("stage") == "full"]
            if len(full) > 1:
                raise ValueError(f"Duplicate full fit for {event_id}/{model}/{weighting}.")
            fit = full[0] if full else None
            if any(not isinstance(r.get("success"), bool) for r in matches):
                raise ValueError("Fit success must be Boolean.")
            folds = [r for r in matches if r.get("stage") == "leave_one_out"]
            indices = [r.get("held_out_station_index") for r in folds]
            if len(set(indices)) != len(indices) or any(
                isinstance(i, bool)
                or not isinstance(i, int)
                or station_count is None
                or not 0 <= i < station_count
                for i in indices
            ):
                raise ValueError("Duplicate or invalid held-out fold index.")
            successful = {r["held_out_station_index"]: r for r in folds if r["success"]}
            heldout = [
                r
                for r in station_records
                if r.get("stage") == "leave_one_out"
                and r.get("model") == model
                and r.get("weighting") == weighting
            ]
            heldout_indices = [r.get("station_index") for r in heldout]
            if len(set(heldout_indices)) != len(heldout_indices) or any(
                i not in successful for i in heldout_indices
            ):
                raise ValueError("Held-out predictions must map uniquely to successful folds.")
            complete = station_count is not None and (
                set(successful) == set(range(station_count)) == set(heldout_indices)
            )
            residuals = []
            normalized = []
            for residual_row in heldout:
                residual = _number(residual_row["residual_ns"])
                sigma = _number(residual_row["timing_uncertainty_ns"])
                if residual is None or sigma is None or sigma <= 0:
                    raise ValueError("Held-out residuals require finite values and positive sigma.")
                residuals.append(residual)
                normalized.append(residual / sigma)
            shifts = [
                _number(r.get("direction_shift_from_full_deg"), nonnegative=True)
                for r in successful.values()
            ]
            shifts = [value for value in shifts if value is not None]
            flags = sorted({str(flag) for r in matches for flag in r.get("quality_flags", [])})
            full_success = fit is not None and fit["success"]
            status = "missing_outcome" if outcome is None else str(outcome.get("status", "unknown"))
            row = {
                "event_id": event_id,
                "model": model,
                "weighting": weighting,
                "previous_development": previous,
                "checkpoint_status": status,
                "prediction_available": prediction is not None,
                "outcome_available": outcome is not None,
                "number_of_stations": station_count,
                "full_attempted": fit is not None,
                "full_success": full_success,
                "full_failure_type": None
                if full_success
                else (fit.get("failure_type") if fit is not None else "MissingFullFit"),
                "heldout_expected_count": station_count,
                "heldout_attempted_count": len(folds),
                "heldout_successful_count": len(successful),
                "heldout_prediction_count": len(heldout),
                "heldout_complete": complete,
                "influence_complete": station_count is not None and len(shifts) == station_count,
                "maximum_observed_loo_direction_shift_deg": max(shifts) if shifts else None,
                "influence_warning": bool(shifts and max(shifts) > INFLUENCE_WARNING_DEG),
                "quality_flags": json.dumps(flags),
                "has_quality_flags": bool(flags),
                "nested_objective_violation": bool(
                    full_success and fit.get("nested_objective_violation")
                ),
                "failure_type": None if outcome is None else outcome.get("failure_type"),
                "failure_message": None if outcome is None else outcome.get("failure_message"),
            }
            for metric in ("reduced_chi_square", "rms_residual_ns"):
                row[metric] = _number(fit.get(metric), nonnegative=True) if full_success else None
            reference = comparisons.get((model, weighting), {})
            row["separation_from_auger_deg"] = (
                _number(reference.get("separation_from_auger_deg"), nonnegative=True)
                if full_success
                else None
            )
            row["direction_frame_version"] = (
                direction_frame_version if row["separation_from_auger_deg"] is not None else None
            )
            with np.errstate(over="raise", invalid="raise"):
                row["heldout_rms_ns"] = (
                    float(np.sqrt(np.mean(np.square(residuals)))) if complete else None
                )
                row["heldout_normalized_mse"] = (
                    float(np.mean(np.square(normalized))) if complete else None
                )
            row["maximum_loo_direction_shift_deg"] = (
                max(shifts) if row["influence_complete"] else None
            )
            output.append(row)
    return output


def _summaries(metrics: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    methods = []
    pairs = []
    for group in GROUPS:
        group_frame = _selected(metrics, group)
        for model in MODELS:
            for weighting in WEIGHTINGS:
                frame = group_frame[
                    (group_frame["model"] == model) & (group_frame["weighting"] == weighting)
                ]
                summary = {
                    "group": group,
                    "model": model,
                    "weighting": weighting,
                    "configured_events": len(frame),
                    "full_attempted_events": int(frame["full_attempted"].sum()),
                    "full_successful_events": int(frame["full_success"].sum()),
                    "full_failed_events": int(
                        (frame["full_attempted"] & ~frame["full_success"]).sum()
                    ),
                    "missing_full_events": int((~frame["full_attempted"]).sum()),
                    "complete_heldout_events": int(frame["heldout_complete"].sum()),
                    "incomplete_heldout_events": int((~frame["heldout_complete"]).sum()),
                    "heldout_expected_folds_known": int(
                        frame["heldout_expected_count"].fillna(0).sum()
                    ),
                    "events_with_unknown_expected_folds": int(
                        frame["heldout_expected_count"].isna().sum()
                    ),
                    "heldout_attempted_folds": int(frame["heldout_attempted_count"].sum()),
                    "heldout_successful_folds": int(frame["heldout_successful_count"].sum()),
                    "flagged_events": int(frame["has_quality_flags"].sum()),
                    "influence_warning_events": int(frame["influence_warning"].sum()),
                    "influence_complete_events": int(frame["influence_complete"].sum()),
                    "nested_objective_violation_events": int(
                        frame["nested_objective_violation"].sum()
                    ),
                }
                for metric in METRICS:
                    values = frame[metric].dropna().to_numpy(dtype=float)
                    summary[f"{metric}_eligible_events"] = len(values)
                    for label, quantile in (("median", 0.5), ("p68", 0.68), ("p95", 0.95)):
                        summary[f"{metric}_{label}"] = (
                            float(np.quantile(values, quantile, method="linear"))
                            if len(values)
                            else None
                        )
                methods.append(summary)
        for weighting in WEIGHTINGS:
            selected = group_frame[group_frame["weighting"] == weighting]
            plane = selected[selected["model"] == "plane"].set_index("event_id")
            quadratic = selected[selected["model"] == "quadratic"].set_index("event_id")
            for metric in METRICS:
                eligible = plane[metric].notna() & quadratic[metric].notna()
                delta = plane.loc[eligible, metric] - quadratic.loc[eligible, metric]
                pairs.append(
                    {
                        "group": group,
                        "weighting": weighting,
                        "metric": metric,
                        "configured_events": len(plane),
                        "paired_complete_events": len(delta),
                        "incomplete_events": len(plane) - len(delta),
                        "quadratic_lower_events": int((delta > 0).sum()),
                        "plane_lower_events": int((delta < 0).sum()),
                        "equal_events": int((delta == 0).sum()),
                        "median_plane_minus_quadratic": float(delta.median())
                        if len(delta)
                        else None,
                    }
                )
    return methods, pairs


def _figures(directory: Path, metrics: pd.DataFrame, *, legacy: bool = False) -> None:
    """Use event-level points, retaining the focus on baseline timing weighting."""
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    descriptions = (
        ("reduced_chi_square", "Nominal reduced chi-square"),
        ("heldout_rms_ns", "Complete conditional held-out RMS (ns)"),
        ("separation_from_auger_deg", "Separation from Auger reference (deg)"),
    )
    selected = metrics[metrics["weighting"] == "timing"]
    for axis, (metric, label) in zip(axes, descriptions, strict=True):
        paired = selected.pivot(index="event_id", columns="model", values=metric).dropna()
        if not paired.empty:
            axis.scatter(paired["plane"], paired["quadratic"], s=20, alpha=0.65)
            maximum = max(float(paired.max().max()), 1e-12)
            axis.plot([0, maximum], [0, maximum], "--", color="0.5", linewidth=1)
        axis.set(
            xlabel=f"Plane: {label}",
            ylabel=f"Quadratic: {label}",
            title=f"{len(paired)} complete training-event pairs",
        )
        axis.grid(alpha=0.2)
    figure.suptitle(
        "LEGACY / HISTORICAL ONLY — reference separations use mismatched frames"
        if legacy
        else "Training-only, Auger-core-assisted comparison — common-frame reference directions"
    )
    temporary = directory / ".training_comparison.tmp.png"
    try:
        figure.savefig(temporary, dpi=160)
        os.replace(temporary, directory / "training_comparison.png")
    finally:
        plt.close(figure)
        temporary.unlink(missing_ok=True)


def build_report(run_dir: Path, *, allow_legacy_reference_frame: bool = False) -> dict:
    """Build derived reports without opening raw data or protected checkpoints.

    Missing checkpoints remain explicit missing rows. Hash mismatches are hard
    failures rather than silently omitted data. Re-running replaces only files
    inside ``report/``; original configurations/checkpoints remain untouched.
    Old unrotated comparisons fail closed. An explicit historical reproduction
    opt-in writes only ``report_legacy_frame/`` and labels every reference metric
    as legacy. It never transforms, mixes, or relabels old values as corrected.
    """
    run_dir = Path(run_dir).resolve()
    configuration, configuration_sha256 = _envelope(run_dir / "configuration.json", run_dir)
    stored_version = configuration.get("direction_frame_version")
    legacy = stored_version in (None, LEGACY_DIRECTION_FRAME_VERSION)
    if stored_version != DIRECTION_FRAME_VERSION and not legacy:
        raise ValueError("Unknown reference-direction frame version in configuration.")
    if legacy and not allow_legacy_reference_frame:
        raise ValueError(
            "Legacy reference-direction frame: use corrected checkpoints or explicitly set "
            "allow_legacy_reference_frame=True for historical reproduction only."
        )
    frame_version = LEGACY_DIRECTION_FRAME_VERSION if legacy else DIRECTION_FRAME_VERSION
    raw_ids = configuration.get("training_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("Configuration must contain a nonempty training_ids list.")
    training_ids = [canonical_event_id(value) for value in raw_ids]
    if len(set(training_ids)) != len(training_ids):
        raise ValueError("Configured training identifiers are not unique.")
    previous_ids = {
        canonical_event_id(value) for value in configuration.get("previous_development_ids", [])
    }
    rows = []
    checkpoint_hashes = {}
    for event_id in training_ids:
        loaded = {}
        for name in ("predictions", "outcome"):
            path = run_dir / "events" / event_id / f"{name}.json"
            if not path.exists():
                loaded[name] = None
                continue
            payload, digest = _envelope(path, run_dir)
            if canonical_event_id(payload.get("event_id")) != event_id:
                raise ValueError(f"Checkpoint event identity mismatch: {path}.")
            if (
                name == "predictions"
                and payload.get("configuration_sha256") != configuration_sha256
            ):
                raise ValueError(f"Prediction configuration mismatch: {path}.")
            if name == "outcome" and payload.get("configuration_sha256") != configuration_sha256:
                raise ValueError(f"Outcome configuration mismatch: {path}.")
            if name == "outcome":
                valid_versions = (
                    (None, LEGACY_DIRECTION_FRAME_VERSION) if legacy else (DIRECTION_FRAME_VERSION,)
                )
                if payload.get("direction_frame_version") not in valid_versions:
                    raise ValueError(f"Mixed or incompatible reference-direction frame: {path}.")
                if any(
                    row.get("direction_frame_version") not in valid_versions
                    for row in payload.get("reference_comparisons", [])
                ):
                    raise ValueError(f"Mixed reference-comparison row frame: {path}.")
            loaded[name] = payload
            checkpoint_hashes[str(path.relative_to(run_dir))] = digest
        outcome = loaded["outcome"]
        if outcome is not None:
            requires_prediction = outcome.get("status") in ("complete", "reference_failed")
            if requires_prediction and loaded["predictions"] is None:
                raise ValueError(f"Outcome requires a missing prediction checkpoint: {event_id}.")
            expected_prediction = outcome.get("prediction_sha256")
            if expected_prediction is not None or requires_prediction:
                prediction_hash = checkpoint_hashes.get(f"events/{event_id}/predictions.json")
                if expected_prediction is None or expected_prediction != prediction_hash:
                    raise ValueError(f"Outcome/prediction hash binding mismatch: {event_id}.")
            if outcome.get("reference_comparisons"):
                reference_path = run_dir / "events" / event_id / "reference_evaluation.json"
                reference, reference_hash = _envelope(reference_path, run_dir)
                if reference_hash != outcome.get("reference_evaluation_sha256"):
                    raise ValueError(f"Outcome/reference hash binding mismatch: {event_id}.")
                if (
                    canonical_event_id(reference.get("event_id")) != event_id
                    or reference.get("configuration_sha256") != configuration_sha256
                    or reference.get("prediction_sha256") != expected_prediction
                    or reference.get("direction_frame_version") not in valid_versions
                    or reference.get("reference_comparisons") != outcome["reference_comparisons"]
                ):
                    raise ValueError(
                        f"Reference identity, frame, or comparison binding mismatch: {event_id}."
                    )
                if not legacy:
                    metadata = reference.get("direction_frame_metadata", {})
                    sky = np.asarray(reference.get("reference_sky_direction_site"), dtype=float)
                    if (
                        not isinstance(metadata, dict)
                        or metadata.get("method_version") != DIRECTION_FRAME_VERSION
                        or sky.shape != (3,)
                        or not np.isfinite(sky).all()
                        or not np.isclose(np.linalg.norm(sky), 1.0, rtol=0.0, atol=1e-12)
                    ):
                        raise ValueError(
                            f"Invalid common-frame reference metadata/vector: {event_id}."
                        )
                checkpoint_hashes[str(reference_path.relative_to(run_dir))] = reference_hash
        rows.extend(
            _event_rows(
                event_id,
                loaded["predictions"],
                loaded["outcome"],
                event_id in previous_ids,
                frame_version,
            )
        )
    metrics = pd.DataFrame(rows)
    methods, pairs = _summaries(metrics)
    for row in methods:
        row["direction_frame_version"] = (
            frame_version if row["separation_from_auger_deg_eligible_events"] else None
        )
    for row in pairs:
        row["direction_frame_version"] = (
            frame_version
            if row["metric"] == "separation_from_auger_deg" and row["paired_complete_events"]
            else None
        )
    statuses = metrics.drop_duplicates("event_id")["checkpoint_status"].value_counts().to_dict()
    summary = {
        "run_id": configuration.get("run_id"),
        "configuration_sha256": configuration_sha256,
        "direction_frame_version": frame_version,
        "legacy_reference_frame": legacy,
        "configured_training_events": len(training_ids),
        "previous_development_events": len(set(training_ids) & previous_ids),
        "checkpoint_status_counts": {str(k): int(v) for k, v in statuses.items()},
        "source_hashes": configuration.get("source_hashes", {}),
        "checkpoint_payload_hashes": checkpoint_hashes,
        "influence_warning_deg": INFLUENCE_WARNING_DEG,
        "quantile_method": "linear interpolation over event-level metrics",
        "method_summary": methods,
        "paired_summary": pairs,
        "claim_limits": (
            "Training/development sample; not held-out validation. Official core and selection "
            "are inherited. Reference agreement is not true-direction accuracy. Conditional "
            "station holdout does not refit the official core or station selection."
        ),
    }
    destination = run_dir / ("report_legacy_frame" if legacy else "report")
    if destination.exists() and not destination.resolve().is_relative_to(run_dir):
        raise ValueError("Report directory escapes its run directory.")
    destination.mkdir(exist_ok=True)
    for name, frame in (
        ("training_event_metrics.csv", metrics),
        ("training_method_summary.csv", pd.DataFrame(methods)),
        ("training_paired_summary.csv", pd.DataFrame(pairs)),
    ):
        _write_bytes(destination / name, frame.to_csv(index=False).encode())
    _write_bytes(
        destination / "summary.json",
        (json.dumps(summary, indent=2, allow_nan=False) + "\n").encode(),
    )
    lines = [
        "# Training-pilot baseline report",
        "",
        f"Reference frame: `{frame_version}`. "
        + (
            "HISTORICAL ONLY: these separations compare mismatched frames."
            if legacy
            else "Reference directions rotated into central-site ENU before comparison."
        ),
        "",
        f"Run: `{summary['run_id']}`. Configured training events: **{len(training_ids)}**; "
        f"previously examined development events: **{summary['previous_development_events']}**.",
        "",
        "This is an Auger-core-assisted training/development comparison, not independent "
        "validation or a measurement of true-direction accuracy. No protected checkpoints or "
        "raw event files are read by this reporting module.",
        "",
        "## Checkpoint and fit accounting",
        "",
        "Event checkpoint statuses: "
        f"`{json.dumps(summary['checkpoint_status_counts'], sort_keys=True)}`.",
        "",
        "| Timing-weighted method | Full success / configured | Complete held-out events | "
        "Any quality flag | Observed influence >1 degree |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in methods:
        if item["group"] == "all_training" and item["weighting"] == "timing":
            lines.append(
                f"| {item['model']} | {item['full_successful_events']} / "
                f"{item['configured_events']} "
                f"| {item['complete_heldout_events']} | {item['flagged_events']} "
                f"| {item['influence_warning_events']} |"
            )
    lines += ["", "## Paired observations", ""]
    for item in pairs:
        if item["group"] == "all_training" and item["weighting"] == "timing":
            lines.append(
                f"- `{item['metric']}`: {item['paired_complete_events']} complete pairs; "
                f"quadratic lower in {item['quadratic_lower_events']}, plane lower in "
                f"{item['plane_lower_events']}, equal in {item['equal_events']}; "
                f"{item['incomplete_events']} incomplete."
            )
    lines += [
        "",
        "## Interpretation and limitations",
        "",
        "CSV summaries report median, p68 and p95 with metric-specific eligible-event counts. "
        "Each event has equal weight: station residuals are summarized within an event before "
        "cross-event summaries. Previously examined and remaining training events are also "
        "reported separately, alongside actual station-multiplicity groups 6, 7–9, 10–19, "
        "20+, under 6, and unknown (including failures with no validated station count). "
        "Missing/failed events are retained; no quality flag or influence "
        "warning excludes an event from primary metrics.",
        "",
        "Full-fit reduced chi-square is nominal, especially at the nonnegative curvature "
        "boundary. Uniform fits do not minimize physical chi-square. Held-out normalized MSE "
        "uses detector timing uncertainties only and is neither reduced chi-square nor a "
        "calibrated predictive pull. Complete held-out metrics require every station fold to "
        "succeed and yield a prediction. Maximum observed influence from incomplete folds is "
        "a lower bound; only complete influence values enter quantile summaries.",
        "",
        "A lower separation means closer agreement with Auger's published direction, not "
        "proof of improvement relative to physical truth or superiority over Auger. The core "
        "and station selection are reused from the full official reconstruction, so station "
        "holdout is conditional rather than independent end-to-end validation. Win counts "
        "alone do not establish statistical significance. Failures and flagged outcomes "
        "must be examined before promoting or tuning a model.",
        "",
        "![Paired training-event diagnostics](training_comparison.png)",
        "",
    ]
    _write_bytes(destination / "scientific_report.md", "\n".join(lines).encode())
    _figures(destination, metrics, legacy=legacy)
    return summary
