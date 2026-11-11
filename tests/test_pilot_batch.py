"""Training isolation, failure accounting, and crash-safe checkpoint contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pytest

from auger_reco.evaluation import pilot_batch as batch
from auger_reco.physics.curved_front import QuadraticFrontFitOptions
from auger_reco.physics.plane_front import PlaneFrontFitOptions

TRAIN = "000000000001"
VALIDATION = "000000000002"
TEST = "000000000003"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    (root / "src/auger_reco").mkdir(parents=True)
    (root / "src/auger_reco/example.py").write_text("# Frozen test source.\n")
    manifest = root / "execution.csv"
    manifest.write_text(
        "event_id,split,release,path\n"
        + "".join(
            f"{identity},{split},3,data/raw/events/Auger_{identity}.json\n"
            for identity, split in ((TRAIN, "train"), (VALIDATION, "validation"), (TEST, "test"))
        )
    )
    contract = root / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "event_count": 3,
                "execution_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "plane_options": asdict(PlaneFrontFitOptions()),
                "quadratic_options": asdict(QuadraticFrontFitOptions()),
            }
        )
    )
    expected = hashlib.sha256(contract.read_bytes()).hexdigest()
    protocol = batch.load_protocol(root, contract, manifest, expected_contract_sha256=expected)
    run_dir = tmp_path / "run"
    calls = []

    def download(identity, directory):
        assert identity == TRAIN, "Protected event reached the downloader!"
        calls.append(identity)
        raw = directory / f"Auger_{identity}.json"
        return {"status": "already_present", "sha256": batch._file_hash(raw), "errors": []}

    monkeypatch.setattr(batch, "download_event", download)
    _write_event(root, 8)
    return protocol, run_dir, calls, contract, manifest, expected


def _write_event(root, count, *, invalid_input=False, invalid_reference=False):
    rng = np.random.default_rng(37)
    positions = rng.uniform(-1500, 1500, (count, 3))
    positions[:, 2] *= 0.01
    sky = np.array([0.3, -0.4, np.sqrt(0.75)])
    times = 1e6 - positions @ sky / 0.299792458
    stations = [
        {
            "id": i + 10,
            "name": f"S{i}",
            "x": p[0],
            "y": p[1],
            "z": p[2],
            "t": t,
            "dt": 10.0,
            "isSelected": 1,
        }
        for i, (p, t) in enumerate(zip(positions, times, strict=True))
    ]
    if invalid_input:
        stations[0]["dt"] = -1
    document = {
        "meta": {"release": 1, "format": 2},
        "info": {"id": int(TRAIN), "date": "2008-07-03T10:05:59Z"},
        "flags": {"sd1500": 1, "sd750": 0},
        "sdrec": {
            "easting": 497256.66,
            "northing": 6099203.68,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "theta": 30.0,
            "phi": -1.0 if invalid_reference else 306.869897645844,
        },
        "stations": stations,
    }
    raw = root / f"data/raw/events/Auger_{TRAIN}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(document))


def _prepare(setup):
    protocol, run_dir, *_ = setup
    _, digest = batch.prepare_run(protocol, run_dir)
    return protocol, run_dir, digest


@pytest.mark.parametrize("identity", [VALIDATION, TEST, "../../etc", "999999999999"])
def test_protected_or_unknown_event_blocked_before_download_or_checkpoint(setup, identity):
    protocol, run_dir, digest = _prepare(setup)
    with pytest.raises(batch.ProtectedSplitError):
        batch.process_event(protocol, run_dir, identity, digest)
    assert setup[2] == []
    assert not (run_dir / "events").exists()


def test_real_fits_prediction_barrier_and_idempotent_resume(setup, monkeypatch):
    protocol, run_dir, digest = _prepare(setup)
    original = batch.direction_reference.load_auger_site_direction_reference

    def guarded_reference(path):
        prediction, _ = batch.read_checkpoint(run_dir / "events" / TRAIN / "predictions.json")
        assert len(prediction["records"]) == 36
        assert prediction["fit_configuration"]["reference_direction_used"] is False
        return original(path)

    monkeypatch.setattr(
        batch.direction_reference, "load_auger_site_direction_reference", guarded_reference
    )
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["status"] == "complete"
    assert len(outcome["reference_comparisons"]) == 4
    assert outcome["fit_attempt_count"] == 36
    assert outcome["direction_frame_version"] == batch.direction_reference.DIRECTION_FRAME_VERSION
    evaluation, _ = batch.read_checkpoint(run_dir / "events" / TRAIN / "reference_evaluation.json")
    reference = original(protocol.root / f"data/raw/events/Auger_{TRAIN}.json")
    np.testing.assert_array_equal(
        evaluation["reference_sky_direction_site"], reference.sky_direction_site
    )
    assert evaluation["direction_frame_metadata"] == reference.frame_metadata
    prediction, _ = batch.read_checkpoint(run_dir / "events" / TRAIN / "predictions.json")
    first = prediction["records"][0]
    expected = batch.angular_separation_deg(
        np.array([first["sky_x"], first["sky_y"], first["sky_z"]]), reference.sky_direction_site
    )
    assert outcome["reference_comparisons"][0]["separation_from_auger_deg"] == expected
    assert expected > 0.01  # A deliberately offset core makes a missing rotation detectable.

    def forbidden(*args, **kwargs):
        pytest.fail("Completed event was refitted or re-evaluated")

    monkeypatch.setattr(batch, "compare_event_fronts", forbidden)
    monkeypatch.setattr(batch.direction_reference, "load_auger_site_direction_reference", forbidden)
    assert batch.process_event(protocol, run_dir, TRAIN, digest) == outcome
    assert setup[2] == [TRAIN]


def test_crash_after_predictions_resumes_without_refitting(setup, monkeypatch):
    protocol, run_dir, digest = _prepare(setup)
    original = batch.direction_reference.load_auger_site_direction_reference

    def crash(path):
        raise RuntimeError("Simulated interruption before reference evaluation")

    monkeypatch.setattr(batch.direction_reference, "load_auger_site_direction_reference", crash)
    with pytest.raises(RuntimeError, match="Simulated interruption"):
        batch.process_event(protocol, run_dir, TRAIN, digest)
    assert (run_dir / "events" / TRAIN / "predictions.json").exists()
    assert not (run_dir / "events" / TRAIN / "outcome.json").exists()
    monkeypatch.setattr(batch.direction_reference, "load_auger_site_direction_reference", original)
    monkeypatch.setattr(batch, "compare_event_fronts", lambda *a, **k: pytest.fail("Refitted"))
    assert batch.process_event(protocol, run_dir, TRAIN, digest)["status"] == "complete"
    assert setup[2] == [TRAIN]


def test_crash_after_reference_resumes_without_re_evaluation(setup, monkeypatch):
    protocol, run_dir, digest = _prepare(setup)
    original = batch.write_checkpoint

    def crash(path, payload):
        if path.name == "outcome.json":
            raise RuntimeError("Interrupted at final publication")
        return original(path, payload)

    monkeypatch.setattr(batch, "write_checkpoint", crash)
    with pytest.raises(RuntimeError, match="Interrupted"):
        batch.process_event(protocol, run_dir, TRAIN, digest)
    assert (run_dir / "events" / TRAIN / "reference_evaluation.json").exists()
    monkeypatch.setattr(batch, "write_checkpoint", original)
    monkeypatch.setattr(
        batch.direction_reference,
        "load_auger_site_direction_reference",
        lambda *a: pytest.fail("Re-evaluated"),
    )
    assert batch.process_event(protocol, run_dir, TRAIN, digest)["status"] == "complete"


def test_six_station_quadratic_fold_failures_are_retained(setup):
    protocol, run_dir, digest = _prepare(setup)
    _write_event(protocol.root, 6)
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["fit_attempt_count"] == 28
    assert outcome["fit_failure_counts"] == {"InsufficientStations": 12}
    assert outcome["successful_fit_count"] == 16


@pytest.mark.parametrize("stage", ["input", "reference"])
def test_bad_data_is_terminal_and_predictions_survive_reference_failure(setup, stage):
    protocol, run_dir, digest = _prepare(setup)
    _write_event(
        protocol.root, 8, invalid_input=stage == "input", invalid_reference=stage == "reference"
    )
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["status"] == f"{stage}_failed"
    assert (run_dir / "events" / TRAIN / "predictions.json").exists() == (stage == "reference")
    assert batch.process_event(protocol, run_dir, TRAIN, digest) == outcome
    assert setup[2] == [TRAIN]


def test_download_failure_terminal_without_event_read(setup, monkeypatch):
    protocol, run_dir, digest = _prepare(setup)
    monkeypatch.setattr(
        batch, "download_event", lambda *a: {"status": "failed", "errors": ["timeout"]}
    )
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["status"] == "download_failed"
    monkeypatch.setattr(batch, "download_event", lambda *a: pytest.fail("Retried failure"))
    assert batch.process_event(protocol, run_dir, TRAIN, digest) == outcome


@pytest.mark.parametrize("target", ["raw", "predictions", "source"])
def test_resume_detects_tampering(setup, target):
    protocol, run_dir, digest = _prepare(setup)
    batch.process_event(protocol, run_dir, TRAIN, digest)
    if target == "source":
        (protocol.root / "src/auger_reco/example.py").write_text("# Changed source\n")
        with pytest.raises(batch.CheckpointIntegrityError):
            batch.prepare_run(protocol, run_dir)
    else:
        if target == "raw":
            path = protocol.root / f"data/raw/events/Auger_{TRAIN}.json"
            path.write_text(path.read_text() + " ")
        else:
            path = run_dir / "events" / TRAIN / "predictions.json"
            envelope = json.loads(path.read_bytes())
            envelope["payload"]["records"][0]["success"] = False
            path.write_text(json.dumps(envelope))
        with pytest.raises(batch.CheckpointIntegrityError):
            batch.process_event(protocol, run_dir, TRAIN, digest)


def test_manifest_tampering_rejected(setup):
    protocol, _, _, contract, manifest, expected = setup
    manifest.write_text(
        manifest.read_text().replace(f"{VALIDATION},validation", f"{VALIDATION},train")
    )
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.load_protocol(protocol.root, contract, manifest, expected_contract_sha256=expected)


def test_batch_training_only_and_repeat_has_no_duplicate_fits(setup):
    protocol, run_dir, *_ = setup
    first = batch.run_batch(protocol, run_dir, workers=1, max_events=1)
    second = batch.run_batch(protocol, run_dir, workers=1)
    assert first["terminal_events"] == second["terminal_events"] == 1
    assert first["protected_events_accessed"] == 0
    assert {p.name for p in (run_dir / "events").iterdir()} == {TRAIN}
    assert setup[2] == [TRAIN]


def test_checkpoint_handles_nonfinite_diagnostics_without_invalid_json(tmp_path):
    path = tmp_path / "checkpoint.json"
    batch.write_checkpoint(path, {"cost": np.inf, "vector": np.array([1.0, np.nan])})
    payload, _ = batch.read_checkpoint(path)
    assert payload["cost"] is None
    assert payload["vector"] == [1.0, None]
    assert payload["serialization_nonfinite_fields"] == ["/cost", "/vector/1"]
    with pytest.raises(FileExistsError):
        batch.write_checkpoint(path, {"new": "must not replace"})


@pytest.mark.parametrize("missing", ["download.json", "predictions.json"])
def test_orphaned_checkpoints_block_resume_without_redownload(setup, missing):
    protocol, run_dir, digest = _prepare(setup)
    batch.process_event(protocol, run_dir, TRAIN, digest)
    (run_dir / "events" / TRAIN / missing).unlink()
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.process_event(protocol, run_dir, TRAIN, digest)
    assert setup[2] == [TRAIN]


def test_mixed_download_chain_detected_even_with_valid_envelope_hash(setup):
    protocol, run_dir, digest = _prepare(setup)
    batch.process_event(protocol, run_dir, TRAIN, digest)
    path = run_dir / "events" / TRAIN / "download.json"
    receipt, _ = batch.read_checkpoint(path)
    receipt["receipt"]["status"] = "downloaded"
    path.unlink()
    batch.write_checkpoint(path, receipt)
    with pytest.raises(batch.CheckpointIntegrityError, match="Prediction input/download"):
        batch.process_event(protocol, run_dir, TRAIN, digest)


def test_unexpected_fit_error_aborts_but_is_resumable(setup, monkeypatch):
    protocol, run_dir, digest = _prepare(setup)
    original = batch.compare_event_fronts

    def crash(*args, **kwargs):
        raise RuntimeError("Unexpected programming error")

    monkeypatch.setattr(batch, "compare_event_fronts", crash)
    with pytest.raises(RuntimeError, match="programming error"):
        batch.process_event(protocol, run_dir, TRAIN, digest)
    assert not (run_dir / "events" / TRAIN / "outcome.json").exists()
    monkeypatch.setattr(batch, "compare_event_fronts", original)
    assert batch.process_event(protocol, run_dir, TRAIN, digest)["status"] == "complete"
    assert setup[2] == [TRAIN]


def test_single_writer_lock_rejects_concurrent_run(setup):
    import fcntl

    protocol, run_dir, _ = _prepare(setup)
    with (run_dir / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already writing"):
            batch.run_batch(protocol, run_dir)


def test_degenerate_geometry_retains_all_failed_fit_rows(setup):
    protocol, run_dir, digest = _prepare(setup)
    path = protocol.root / f"data/raw/events/Auger_{TRAIN}.json"
    document = json.loads(path.read_bytes())
    for station in document["stations"]:
        station.update(x=0.0, y=0.0, z=0.0)
    path.write_text(json.dumps(document))
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["status"] == "complete"
    assert outcome["fit_attempt_count"] == 36
    assert outcome["successful_fit_count"] == 0
    assert outcome["reference_comparisons"] == []


@pytest.mark.parametrize("workers,max_events", [(0, None), (True, None), (1, 0), (1, True)])
def test_invalid_execution_budgets_rejected(setup, workers, max_events):
    protocol, run_dir, *_ = setup
    with pytest.raises(ValueError):
        batch.run_batch(protocol, run_dir, workers=workers, max_events=max_events)


def test_legacy_configuration_cannot_be_resumed_or_overwritten(setup):
    protocol, run_dir, _ = _prepare(setup)
    path = run_dir / "configuration.json"
    payload, _ = batch.read_checkpoint(path)
    payload.pop("direction_frame_version")
    path.unlink()
    batch.write_checkpoint(path, payload)
    before = path.read_bytes()
    with pytest.raises(batch.CheckpointIntegrityError, match="Legacy or incompatible"):
        batch.prepare_run(protocol, run_dir)
    assert path.read_bytes() == before
    assert setup[2] == []
    _, legacy_hash = batch.read_checkpoint(path)
    with pytest.raises(batch.CheckpointIntegrityError, match="Legacy or incompatible"):
        batch.process_event(protocol, run_dir, TRAIN, legacy_hash)
    assert setup[2] == []


@pytest.mark.parametrize("checkpoint", ["reference_evaluation", "outcome"])
def test_legacy_event_checkpoint_cannot_be_reused(setup, checkpoint):
    protocol, run_dir, digest = _prepare(setup)
    batch.process_event(protocol, run_dir, TRAIN, digest)
    path = run_dir / "events" / TRAIN / f"{checkpoint}.json"
    payload, _ = batch.read_checkpoint(path)
    payload.pop("direction_frame_version")
    path.unlink()
    batch.write_checkpoint(path, payload)
    before = path.read_bytes()
    with pytest.raises(batch.CheckpointIntegrityError, match="Legacy or incompatible"):
        batch.process_event(protocol, run_dir, TRAIN, digest)
    assert path.read_bytes() == before


def test_missing_core_coordinates_fail_reference_without_losing_predictions(setup):
    protocol, run_dir, digest = _prepare(setup)
    path = protocol.root / f"data/raw/events/Auger_{TRAIN}.json"
    document = json.loads(path.read_bytes())
    document["sdrec"].pop("easting")
    path.write_text(json.dumps(document))
    outcome = batch.process_event(protocol, run_dir, TRAIN, digest)
    assert outcome["status"] == "reference_failed"
    assert outcome["reference_comparisons"] == []
    assert (run_dir / "events" / TRAIN / "predictions.json").is_file()
