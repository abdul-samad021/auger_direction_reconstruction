"""Outcome-independent cohort selection and bounded immutable downloads."""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import urllib.error
from pathlib import Path

import pytest

from auger_reco.data import development_sample as sample


def row(event_id, *, split="train", stations=7, zenith="0-15", multiplicity="6-7"):
    return {
        "event_id": event_id,
        "split": split,
        "selected_stations": stations,
        "zenith_bin": zenith,
        "multiplicity_bin": multiplicity,
    }


def test_selection_deterministic_order_independent_and_round_robin():
    rows = [
        row(i, zenith=z)
        for z in ("0-15", "15-30")
        for i in range(1 if z == "0-15" else 11, 6 if z == "0-15" else 16)
    ]
    first = sample.select_development_events(rows, count=5)
    assert first == sample.select_development_events(reversed(rows), count=5)
    assert [r["zenith_bin"] for r in first] == ["0-15", "15-30", "0-15", "15-30", "0-15"]
    assert len({r["event_id"] for r in first}) == 5
    first_stratum = [r["event_id"] for r in first if r["zenith_bin"] == "0-15"]
    expected = sorted(
        [f"{i:012d}" for i in range(1, 6)],
        key=lambda event_id: hashlib.sha256(f"20261010:{event_id}".encode()).hexdigest(),
    )[:3]
    assert first_stratum == expected


def test_selection_excludes_focus_low_multiplicity_and_other_splits():
    rows = [
        row("081847956000"),
        row(1, stations=6),
        row(2, split="test"),
        row(3, split="validation"),
        row(4),
    ]
    assert sample.select_development_events(rows, count=1) == [row("000000000004")]


def test_selection_does_not_inspect_targets_or_other_split_metadata():
    class Protected(dict):
        def __getitem__(self, key):
            if key not in sample.SELECTION_FIELDS:
                raise AssertionError("A target was inspected!")
            return super().__getitem__(key)

    rows = [Protected(row(1)), {"split": "test"}, {"split": "validation"}]
    assert sample.select_development_events(rows, count=1)[0]["event_id"] == "000000000001"


@pytest.mark.parametrize("value", [True, -1, "1.0", "../../1", "１２", "1234567890123", None])
def test_bad_identifier(value):
    with pytest.raises(ValueError):
        sample.canonical_event_id(value)


@pytest.mark.parametrize("count", [True, 0, -1, 1.5])
def test_bad_sample_size(count):
    with pytest.raises(ValueError):
        sample.select_development_events([row(1)], count=count)


@pytest.mark.parametrize("stations", [True, float("nan"), float("inf"), -1, 7.5])
def test_bad_station_counts(stations):
    with pytest.raises(ValueError):
        sample.select_development_events([row(1, stations=stations)], count=1)


def test_duplicate_and_insufficient_rows_fail_without_partial_result():
    with pytest.raises(ValueError, match="Duplicate"):
        sample.select_development_events([row(1), row("000000000001")], count=1)
    with pytest.raises(ValueError, match="Not enough"):
        sample.select_development_events([row(1)], count=2)


def test_load_rows_projects_columns(tmp_path):
    path = tmp_path / "cohort.csv"
    path.write_text(
        "event_id,split,selected_stations,zenith_bin,multiplicity_bin,secret_target\n"
        "000000000001,train,7.0,0-15,6-7,DO_NOT_USE\n"
    )
    result = sample.load_selection_rows(path)
    assert set(result[0]) == set(sample.SELECTION_FIELDS)
    assert result[0]["event_id"] == "000000000001"


class Response(io.BytesIO):
    def geturl(self):
        return "https://opendata.auger.org/releases/3/data/dataSD1500/Auger_000000000001.json"


def payload(event_id=1):
    return json.dumps({"info": {"id": event_id}, "unused": {"target": "ignored"}}).encode()


def test_download_validates_id_hash_timeout_and_keeps_file(monkeypatch, tmp_path):
    def open_response(request, timeout):
        assert request.full_url == sample.EVENT_URL_TEMPLATE.format(event_id="000000000001")
        assert timeout == 30
        return Response(payload())

    monkeypatch.setattr(sample.urllib.request, "urlopen", open_response)
    record = sample.download_event("000000000001", tmp_path)
    assert record["status"] == "downloaded"
    assert record["sha256"] == hashlib.sha256(payload()).hexdigest()
    assert record["attempts"] == 1
    monkeypatch.setattr(sample.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    again = sample.download_event("000000000001", tmp_path)
    assert again["status"] == "already_present"
    assert again["sha256"] == record["sha256"]


@pytest.mark.parametrize("body", [b"[]", b"not json", payload(2), b"", b'{"info":{}}'])
def test_invalid_download_not_published(monkeypatch, tmp_path, body):
    monkeypatch.setattr(sample.urllib.request, "urlopen", lambda *a, **k: Response(body))
    record = sample.download_event("1", tmp_path)
    assert record["status"] == "failed"
    assert record["attempts"] == 2
    assert not list(tmp_path.iterdir())


def test_oversized_response_fails_and_bad_existing_file_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(sample, "MAX_EVENT_BYTES", 5)
    monkeypatch.setattr(sample.urllib.request, "urlopen", lambda *a, **k: Response(b"123456"))
    assert sample.download_event("1", tmp_path)["status"] == "failed"
    destination = tmp_path / "Auger_000000000001.json"
    destination.write_bytes(b"invalid")
    assert sample.download_event("1", tmp_path)["attempts"] == 0
    assert destination.read_bytes() == b"invalid"


def test_transient_failure_retries_once(monkeypatch, tmp_path):
    calls = []

    def open_response(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError("temporary")
        return Response(payload())

    monkeypatch.setattr(sample.urllib.request, "urlopen", open_response)
    record = sample.download_event("1", tmp_path)
    assert record["status"] == "downloaded"
    assert record["attempts"] == 2
    assert len(record["errors"]) == 1


def test_atomic_publish_never_overwrites_existing_file(tmp_path):
    path = tmp_path / "event.json"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        sample._publish_new_file(path, b"replacement")
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "problem", [urllib.error.URLError("offline"), http.client.IncompleteRead(b"partial")]
)
def test_all_download_attempts_fail_with_diagnostics(monkeypatch, tmp_path, problem):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise problem

    monkeypatch.setattr(sample.urllib.request, "urlopen", fail)
    result = sample.download_event("1", tmp_path)
    assert result["status"] == "failed"
    assert len(calls) == len(result["errors"]) == 2
    assert not list(tmp_path.iterdir())


def test_nonofficial_redirect_is_rejected(monkeypatch, tmp_path):
    class Redirected(Response):
        def geturl(self):
            return "https://unrelated.example/file.json"

    monkeypatch.setattr(sample.urllib.request, "urlopen", lambda *a, **k: Redirected(payload()))
    result = sample.download_event("1", tmp_path)
    assert result["status"] == "failed"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "options",
    [
        {"seed": True},
        {"seed": 1.5},
        {"minimum_stations": 6},
        {"minimum_stations": True},
        {"minimum_stations": 7.5},
    ],
)
def test_invalid_selection_configuration(options):
    with pytest.raises(ValueError):
        sample.select_development_events([row(1)], count=1, **options)


def test_manifest_required_before_network_and_receipt_retains_failures(monkeypatch, tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "not_frozen", "events": [{"event_id": "1"}]}))
    calls = []

    def fake_download(event_id, directory):
        calls.append(event_id)
        return {"event_id": event_id, "status": "failed"}

    monkeypatch.setattr(sample, "download_event", fake_download)
    receipt_path = tmp_path / "receipt.json"
    with pytest.raises(ValueError, match="frozen"):
        sample.download_development_manifest(path, tmp_path, receipt_path)
    assert calls == []
    path.write_text(
        json.dumps({"status": "frozen_before_download_and_fit", "events": [{"event_id": "1"}]})
    )
    receipt = sample.download_development_manifest(path, tmp_path, receipt_path)
    assert calls == ["000000000001"]
    assert receipt["records"] == [{"event_id": "000000000001", "status": "failed"}]
    assert receipt["selection_manifest_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        sample.download_development_manifest(path, tmp_path, receipt_path)


def test_frozen_repository_sample_reproduces_selection():
    root = Path(__file__).resolve().parents[1]
    path = root / "data/manifests/real_front_development_v1.json"
    if not path.exists():
        pytest.skip("Optional frozen development manifest is not present.")
    manifest = json.loads(path.read_text())
    source = root / manifest["source_manifest"]
    if not source.exists():
        pytest.skip("Optional local pilot manifest is not distributed with the code.")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["source_sha256"]
    selected = sample.select_development_events(sample.load_selection_rows(source))
    frozen = [
        {key: row[key] for key in sample.SELECTION_FIELDS}
        for row in manifest["events"]
        if row["role"] == "training_development"
    ]
    assert frozen == selected
    assert len(manifest["events"]) == 20
