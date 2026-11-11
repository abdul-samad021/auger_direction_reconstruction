"""Tests of pairing, denominator accounting and reproducible descriptive inference."""

import csv
import hashlib
import json

import numpy as np
import pytest

from auger_reco.evaluation import conference_synthesis as synthesis


@pytest.mark.parametrize(
    "left,right", [([], []), ([1], [1, 2]), ([[1]], [[1]]), ([np.nan], [1]), ([1], [np.inf])]
)
def test_bad_pairs_rejected(left, right):
    with pytest.raises(ValueError):
        synthesis.paired_summary(left, right)


@pytest.mark.parametrize("resamples", [0, 1, True, 2.5])
def test_invalid_resamples_rejected(resamples):
    with pytest.raises(ValueError):
        synthesis.paired_summary([1, 2], [2, 3], resamples=resamples)


def test_pairing_is_not_difference_of_marginal_medians():
    left = [0, 10, 100]
    right = [1, 100, 10]
    result = synthesis.paired_summary(left, right, resamples=200)
    assert result["median_paired_difference_quadratic_minus_plane"] == 1
    assert np.median(right) - np.median(left) == 0
    assert result["quadratic_lower_count"] == 1
    assert result["quadratic_higher_count"] == 2


def test_constant_paired_effect_has_degenerate_interval_and_exact_reproducibility():
    left = np.arange(12.0)
    first = synthesis.paired_summary(left, left - 3, resamples=300)
    second = synthesis.paired_summary(left, left - 3, resamples=300)
    assert first == second
    assert first["median_paired_difference_bootstrap_95_interval"] == [-3.0, -3.0]
    assert first["quadratic_lower_count"] == 12


def test_single_event_not_given_a_bootstrap_interval():
    result = synthesis.paired_summary([1], [1])
    assert result["median_paired_difference_bootstrap_95_interval"] is None
    assert result["exact_tie_count"] == 1


def _rows():
    rows = []
    for event_id, count in (("000000000001", 6), ("000000000002", 8)):
        for model in ("plane", "quadratic"):
            for weighting in ("timing", "uniform"):
                missing = model == "quadratic" and count == 6
                row = {
                    "event_id": event_id,
                    "model": model,
                    "weighting": weighting,
                    "previous_development": "False",
                    "full_success": "True",
                    "heldout_complete": str(not missing),
                    "influence_complete": str(not missing),
                    "number_of_stations": str(count),
                }
                for metric, (_, _, conditional) in synthesis.METRICS.items():
                    row[metric] = "" if missing and conditional else "2.5"
                rows.append(row)
    return rows


def _write(tmp_path, rows):
    path = tmp_path / "metrics.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_structural_exclusions_remain_visible_and_leading_zeros_preserved(tmp_path):
    records = synthesis.read_metrics(_write(tmp_path, _rows()))
    assert ("000000000001", "plane", "timing") in records
    summaries = synthesis.summarize(records, resamples=10)
    item = next(
        row
        for row in summaries
        if row["group"] == "all_training"
        and row["weighting"] == "timing"
        and row["metric"] == "heldout_rms_ns"
    )
    assert item["eligible_count"] == 2
    assert item["summary"]["n"] == 1
    assert item["excluded_event_ids"] == ["000000000001"]
    empty = next(
        row
        for row in summaries
        if row["group"] == "multiplicity_6"
        and row["weighting"] == "timing"
        and row["metric"] == "heldout_rms_ns"
    )
    assert empty["summary"] is None
    assert empty["eligible_count"] == 1


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "missing",
        "boolean",
        "infinity",
        "negative",
        "station_count",
        "inconsistent_count",
        "identity",
    ],
)
def test_corrupt_metric_tables_fail_closed(tmp_path, change):
    rows = _rows()
    if change == "duplicate":
        rows.append(rows[0].copy())
    elif change == "missing":
        rows.pop()
    elif change == "boolean":
        rows[0]["full_success"] = "no"
    elif change == "infinity":
        rows[0]["reduced_chi_square"] = "inf"
    elif change == "negative":
        rows[0]["rms_residual_ns"] = "-1"
    elif change == "station_count":
        rows[0]["number_of_stations"] = "0"
    elif change == "inconsistent_count":
        rows[0]["number_of_stations"] = "7"
    else:
        rows[0]["event_id"] = "1"
    with pytest.raises(ValueError):
        synthesis.read_metrics(_write(tmp_path, rows))


def test_refuses_to_overwrite_an_existing_analysis(tmp_path):
    source = _write(tmp_path, _rows())
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "original.txt"
    sentinel.write_text("unchanged")
    with pytest.raises(FileExistsError):
        synthesis.run(source, output, configuration=tmp_path / "absent.json")
    assert sentinel.read_text() == "unchanged"


def _configuration(identifiers):
    payload = {"training_ids": identifiers}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return json.dumps(
        {"payload": payload, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}
    ).encode()


def test_valid_training_whitelist():
    assert synthesis.training_ids(_configuration(["000000000001"])) == {"000000000001"}


@pytest.mark.parametrize("ids", [[], ["1"], [1], ["000000000001", "000000000001"]])
def test_invalid_whitelist_rejected(ids):
    with pytest.raises(ValueError):
        synthesis.training_ids(_configuration(ids))


def test_tampered_configuration_rejected():
    damaged = _configuration(["000000000001"]).replace(b"000000000001", b"000000000002")
    with pytest.raises(ValueError, match="checksum"):
        synthesis.training_ids(damaged)


def test_unauthorized_population_refused_before_writing(tmp_path):
    source = _write(tmp_path, _rows())
    configuration = tmp_path / "config.json"
    configuration.write_bytes(_configuration(["000000000001"]))
    output = tmp_path / "unauthorized"
    with pytest.raises(ValueError, match="authorized"):
        synthesis.run(source, output, configuration=configuration)
    assert not output.exists()
