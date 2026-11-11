"""Cheap checkpoint fixtures for event-equal training-only reports."""

import hashlib
import json
from pathlib import Path

import pytest

from auger_reco.evaluation import pilot_reporting as reporting


def envelope(path, payload):
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"payload": payload, "sha256": digest}))
    return digest


def initialize(root, ids=("000000000001", "000000000002")):
    return envelope(
        root / "configuration.json",
        {
            "run_id": "test-pilot",
            "training_ids": list(ids),
            "previous_development_ids": [ids[0]],
            "source_hashes": {"source.py": "sha"},
            "direction_frame_version": reporting.DIRECTION_FRAME_VERSION,
        },
    )


def event(
    root,
    identifier,
    config_hash,
    *,
    count=7,
    residual=2.0,
    failed_quadratic_fold=False,
    flags=(),
    shift=0.2,
):
    records = []
    station_residuals = []
    comparisons = []
    for model in reporting.MODELS:
        scale = 1.0 if model == "plane" else 0.5
        for weighting in reporting.WEIGHTINGS:
            records.append(
                {
                    "stage": "full",
                    "model": model,
                    "weighting": weighting,
                    "success": True,
                    "reduced_chi_square": residual * scale,
                    "rms_residual_ns": residual * scale,
                    "quality_flags": list(flags),
                    "nested_objective_violation": False,
                }
            )
            comparisons.append(
                {
                    "model": model,
                    "weighting": weighting,
                    "separation_from_auger_deg": 0.2 * scale,
                    "direction_frame_version": reporting.DIRECTION_FRAME_VERSION,
                }
            )
            for index in range(count):
                success = not (model == "quadratic" and index == 0 and failed_quadratic_fold)
                records.append(
                    {
                        "stage": "leave_one_out",
                        "model": model,
                        "weighting": weighting,
                        "success": success,
                        "held_out_station_index": index,
                        "direction_shift_from_full_deg": shift if success else None,
                        "quality_flags": list(flags) if success else [],
                        "failure_type": None if success else "InsufficientStations",
                    }
                )
                if success:
                    station_residuals.append(
                        {
                            "stage": "leave_one_out",
                            "model": model,
                            "weighting": weighting,
                            "station_index": index,
                            "residual_ns": residual * scale,
                            "timing_uncertainty_ns": 2.0,
                        }
                    )
    path = root / "events" / identifier
    prediction = {
        "event_id": identifier,
        "configuration_sha256": config_hash,
        "event_metadata": {"number_of_stations": count},
        "records": records,
        "station_residuals": station_residuals,
        "optimizer_attempts": [],
    }
    prediction_hash = envelope(path / "predictions.json", prediction)
    reference_hash = envelope(
        path / "reference_evaluation.json",
        {
            "event_id": identifier,
            "configuration_sha256": config_hash,
            "prediction_sha256": prediction_hash,
            "direction_frame_version": reporting.DIRECTION_FRAME_VERSION,
            "direction_frame_metadata": {"method_version": reporting.DIRECTION_FRAME_VERSION},
            "reference_sky_direction_site": [0.0, 0.0, 1.0],
            "reference_comparisons": comparisons,
        },
    )
    envelope(
        path / "outcome.json",
        {
            "event_id": identifier,
            "configuration_sha256": config_hash,
            "status": "complete",
            "prediction_sha256": prediction_hash,
            "reference_evaluation_sha256": reference_hash,
            "reference_comparisons": comparisons,
            "direction_frame_version": reporting.DIRECTION_FRAME_VERSION,
        },
    )
    return prediction


def method(summary, model="plane", group="all_training"):
    return next(
        row
        for row in summary["method_summary"]
        if row["model"] == model and row["weighting"] == "timing" and row["group"] == group
    )


def pair(summary, metric):
    return next(
        row
        for row in summary["paired_summary"]
        if row["metric"] == metric
        and row["weighting"] == "timing"
        and row["group"] == "all_training"
    )


@pytest.fixture(autouse=True)
def cheap_plot(monkeypatch):
    # Statistical and integrity tests should not spend time rasterizing figures.
    monkeypatch.setattr(reporting, "_figures", lambda directory, frame, **kwargs: None)


def test_event_equal_quantiles_subgroups_and_derived_files(tmp_path):
    digest = initialize(tmp_path)
    event(tmp_path, "000000000001", digest, count=7, residual=2)
    event(tmp_path, "000000000002", digest, count=20, residual=10)
    before = (tmp_path / "configuration.json").read_bytes()
    summary = reporting.build_report(tmp_path)
    assert summary["configured_training_events"] == 2
    assert summary["previous_development_events"] == 1
    assert method(summary)["heldout_rms_ns_median"] == 6.0
    assert method(summary)["heldout_rms_ns_p68"] == pytest.approx(7.44)
    assert method(summary)["heldout_rms_ns_p95"] == pytest.approx(9.6)
    assert method(summary, group="previous_development")["heldout_rms_ns_median"] == 2.0
    assert method(summary, group="remaining_training")["heldout_rms_ns_median"] == 10.0
    assert pair(summary, "heldout_rms_ns")["paired_complete_events"] == 2
    assert pair(summary, "heldout_rms_ns")["quadratic_lower_events"] == 2
    assert (tmp_path / "configuration.json").read_bytes() == before
    for name in (
        "summary.json",
        "scientific_report.md",
        "training_event_metrics.csv",
        "training_method_summary.csv",
        "training_paired_summary.csv",
    ):
        assert (tmp_path / "report" / name).is_file()
    assert reporting.build_report(tmp_path) == summary


def test_incomplete_folds_keep_failure_denominators_and_metric_specific_pairing(tmp_path):
    digest = initialize(tmp_path)
    event(tmp_path, "000000000001", digest, count=6, failed_quadratic_fold=True)
    event(tmp_path, "000000000002", digest, count=7)
    summary = reporting.build_report(tmp_path)
    curved = method(summary, "quadratic")
    assert curved["full_successful_events"] == 2
    assert curved["heldout_attempted_folds"] == 13
    assert curved["heldout_successful_folds"] == 12
    assert curved["complete_heldout_events"] == 1
    assert curved["incomplete_heldout_events"] == 1
    assert pair(summary, "heldout_rms_ns")["paired_complete_events"] == 1
    assert pair(summary, "heldout_rms_ns")["incomplete_events"] == 1
    assert pair(summary, "reduced_chi_square")["paired_complete_events"] == 2


def test_missing_and_failed_events_are_not_dropped(tmp_path):
    configuration_hash = initialize(tmp_path)
    envelope(
        tmp_path / "events/000000000001/outcome.json",
        {
            "event_id": "000000000001",
            "configuration_sha256": configuration_hash,
            "status": "download_failed",
            "direction_frame_version": reporting.DIRECTION_FRAME_VERSION,
            "failure_type": "TimeoutError",
            "failure_message": "timeout",
        },
    )
    summary = reporting.build_report(tmp_path)
    assert summary["checkpoint_status_counts"] == {"download_failed": 1, "missing_outcome": 1}
    assert method(summary)["configured_events"] == 2
    assert method(summary)["missing_full_events"] == 2
    assert method(summary)["events_with_unknown_expected_folds"] == 2
    assert method(summary)["heldout_rms_ns_median"] is None
    assert pair(summary, "separation_from_auger_deg")["paired_complete_events"] == 0


def test_prediction_without_outcome_preserves_timing_but_no_reference(tmp_path):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    (tmp_path / "events/000000000001/outcome.json").unlink()
    summary = reporting.build_report(tmp_path)
    assert method(summary)["full_successful_events"] == 1
    assert pair(summary, "rms_residual_ns")["paired_complete_events"] == 1
    assert pair(summary, "separation_from_auger_deg")["paired_complete_events"] == 0


def test_never_reads_unconfigured_event_or_raw_files(tmp_path, monkeypatch):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    forbidden = tmp_path / "events/000000000999/predictions.json"
    forbidden.parent.mkdir(parents=True)
    forbidden.write_text("not even valid JSON")
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        assert "000000000999" not in str(path)
        assert "data/raw" not in str(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert reporting.build_report(tmp_path)["configured_training_events"] == 1


def test_hash_tamper_stops_report(tmp_path):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    path = tmp_path / "events/000000000001/predictions.json"
    document = json.loads(path.read_text())
    document["payload"]["records"][0]["rms_residual_ns"] = 900
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="integrity mismatch"):
        reporting.build_report(tmp_path)


@pytest.mark.parametrize("change", ["identity", "configuration", "duplicate_fold"])
def test_resealed_invalid_checkpoint_still_rejected(tmp_path, change):
    digest = initialize(tmp_path, ids=("000000000001",))
    prediction = event(tmp_path, "000000000001", digest)
    if change == "identity":
        prediction["event_id"] = "000000000002"
    elif change == "configuration":
        prediction["configuration_sha256"] = "wrong"
    else:
        prediction["records"].append(prediction["records"][1])
    envelope(tmp_path / "events/000000000001/predictions.json", prediction)
    with pytest.raises(ValueError):
        reporting.build_report(tmp_path)


def test_quality_flags_and_influence_do_not_exclude_event(tmp_path):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest, flags=("ill_conditioned", "core_assisted"), shift=1.2)
    summary = reporting.build_report(tmp_path)
    assert method(summary)["flagged_events"] == 1
    assert method(summary)["influence_warning_events"] == 1
    assert method(summary)["heldout_rms_ns_eligible_events"] == 1
    text = (tmp_path / "report/training_event_metrics.csv").read_text()
    assert "ill_conditioned" in text and "core_assisted" in text


def test_partial_influence_is_not_in_complete_quantile(tmp_path):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest, failed_quadratic_fold=True, shift=2.0)
    summary = reporting.build_report(tmp_path)
    assert method(summary, "quadratic")["influence_warning_events"] == 1
    assert method(summary, "quadratic")["maximum_loo_direction_shift_deg_eligible_events"] == 0


def test_no_duplicate_training_identifiers(tmp_path):
    initialize(tmp_path, ids=("000000000001", "1"))
    with pytest.raises(ValueError, match="not unique"):
        reporting.build_report(tmp_path)


def test_legacy_reports_require_opt_in_and_cannot_replace_corrected_reports(tmp_path):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    reporting.build_report(tmp_path)
    corrected_report = tmp_path / "report/training_event_metrics.csv"
    preserved = corrected_report.read_bytes()
    configuration = json.loads((tmp_path / "configuration.json").read_text())["payload"]
    configuration.pop("direction_frame_version")
    legacy_config_hash = envelope(tmp_path / "configuration.json", configuration)
    directory = tmp_path / "events/000000000001"
    prediction = json.loads((directory / "predictions.json").read_text())["payload"]
    prediction["configuration_sha256"] = legacy_config_hash
    prediction_hash = envelope(directory / "predictions.json", prediction)
    outcome = json.loads((directory / "outcome.json").read_text())["payload"]
    outcome.pop("direction_frame_version")
    outcome.update(configuration_sha256=legacy_config_hash, prediction_sha256=prediction_hash)
    for comparison in outcome["reference_comparisons"]:
        comparison.pop("direction_frame_version")
    reference = json.loads((directory / "reference_evaluation.json").read_text())["payload"]
    reference.pop("direction_frame_version")
    reference.update(
        configuration_sha256=legacy_config_hash,
        prediction_sha256=prediction_hash,
        reference_comparisons=outcome["reference_comparisons"],
    )
    outcome["reference_evaluation_sha256"] = envelope(
        directory / "reference_evaluation.json", reference
    )
    envelope(directory / "outcome.json", outcome)
    with pytest.raises(ValueError, match="Legacy reference-direction frame"):
        reporting.build_report(tmp_path)
    summary = reporting.build_report(tmp_path, allow_legacy_reference_frame=True)
    assert summary["legacy_reference_frame"] is True
    assert summary["direction_frame_version"] == reporting.LEGACY_DIRECTION_FRAME_VERSION
    assert corrected_report.read_bytes() == preserved
    legacy_report = tmp_path / "report_legacy_frame/training_event_metrics.csv"
    assert reporting.LEGACY_DIRECTION_FRAME_VERSION in legacy_report.read_text()
    assert "HISTORICAL ONLY" in (tmp_path / "report_legacy_frame/scientific_report.md").read_text()


@pytest.mark.parametrize("level", ["outcome", "comparison"])
def test_mixed_frame_checkpoints_rejected_even_with_legacy_opt_in(tmp_path, level):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    path = tmp_path / "events/000000000001/outcome.json"
    payload = json.loads(path.read_text())["payload"]
    target = payload if level == "outcome" else payload["reference_comparisons"][0]
    target.pop("direction_frame_version")
    envelope(path, payload)
    with pytest.raises(ValueError, match="frame"):
        reporting.build_report(tmp_path, allow_legacy_reference_frame=True)


def test_missing_comparison_rows_have_no_frame_claim(tmp_path):
    import pandas as pd

    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    (tmp_path / "events/000000000001/outcome.json").unlink()
    reporting.build_report(tmp_path)
    frame = pd.read_csv(tmp_path / "report/training_event_metrics.csv")
    assert frame["direction_frame_version"].isna().all()
    assert frame["separation_from_auger_deg"].isna().all()


@pytest.mark.parametrize("change", ["hash", "comparison", "metadata", "vector", "frame"])
def test_sealed_reference_linkage_and_common_frame_checked(tmp_path, change):
    digest = initialize(tmp_path, ids=("000000000001",))
    event(tmp_path, "000000000001", digest)
    directory = tmp_path / "events/000000000001"
    path = directory / "reference_evaluation.json"
    reference = json.loads(path.read_text())["payload"]
    if change in ("hash", "comparison"):
        reference["reference_comparisons"][0]["separation_from_auger_deg"] = 0.99
    elif change == "metadata":
        reference["direction_frame_metadata"]["method_version"] = "unknown"
    elif change == "vector":
        reference["reference_sky_direction_site"] = [1.0, 1.0, 1.0]
    else:
        reference.pop("direction_frame_version")
    reference_hash = envelope(path, reference)
    if change != "hash":
        outcome_path = directory / "outcome.json"
        outcome = json.loads(outcome_path.read_text())["payload"]
        outcome["reference_evaluation_sha256"] = reference_hash
        envelope(outcome_path, outcome)
    with pytest.raises(ValueError, match="reference|Reference"):
        reporting.build_report(tmp_path)
