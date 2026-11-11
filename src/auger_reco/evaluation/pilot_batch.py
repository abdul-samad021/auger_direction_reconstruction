"""Checkpointed, training-only execution of the frozen real-event pilot.

This runner deliberately has no switch to evaluate validation or test events.
Immutable, hash-checked predictions precede every reference-direction read.
An interrupted event resumes from its last published checkpoint; a terminal
failure is retained, never retried or replaced silently. WSL/Linux is required
for the process-lifetime advisory lock (the scientific fitters are portable).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import re
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from auger_reco.data import core_reference, direction_reference, event_json
from auger_reco.data.development_sample import download_event
from auger_reco.evaluation.front_comparison import compare_event_fronts
from auger_reco.physics.curved_front import QuadraticFrontFitOptions
from auger_reco.physics.plane_front import (
    PlaneFrontFitOptions,
    angular_separation_deg,
)

FROZEN_CONTRACT_SHA256 = "cca5dd0253ad119f15177671afc0da5cb53a9a33797f7141c0dc65df6eadc554"
HANDOFF = Path("reports/results/prepilot_diagnostics_20261010T234353_804166Z")
EXECUTION_COLUMNS = ["event_id", "split", "release", "path"]
SCHEMA_VERSION = 2


class CheckpointIntegrityError(RuntimeError):
    """A frozen input, source, or checkpoint no longer matches its binding."""


class ProtectedSplitError(ValueError):
    """An event is not authorized for this training-only runner."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_value(value: Any, path: str, nonfinite: list[str]) -> Any:
    """Preserve undefined diagnostics as null, with an explicit location ledger."""
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        nonfinite.append(path)
        return None
    if isinstance(value, dict):
        return {str(k): _json_value(v, f"{path}/{k}", nonfinite) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v, f"{path}/{i}", nonfinite) for i, v in enumerate(value)]
    return value


def _publish_bytes(path: Path, contents: bytes) -> None:
    """Publish a complete file atomically without overwriting existing work."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pilot-partial-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Same filesystem, atomic; fails if destination exists.
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def write_checkpoint(path: Path, payload: dict[str, Any]) -> str:
    """Seal strict JSON and its content hash in one atomic envelope."""
    nonfinite: list[str] = []
    clean = _json_value(payload, "", nonfinite)
    clean["serialization_nonfinite_fields"] = nonfinite
    digest = _digest(clean)
    envelope = {"payload": clean, "sha256": digest}
    _publish_bytes(path, json.dumps(envelope, indent=2, allow_nan=False).encode() + b"\n")
    return digest


def read_checkpoint(path: Path) -> tuple[dict[str, Any], str]:
    """Reject corrupted/incomplete envelopes rather than silently restarting."""
    try:
        envelope = json.loads(path.read_bytes())
        payload, digest = envelope["payload"], envelope["sha256"]
        if not isinstance(payload, dict) or digest != _digest(payload):
            raise ValueError("Payload hash mismatch")
        return payload, digest
    except (ValueError, KeyError, TypeError) as error:
        raise CheckpointIntegrityError(f"Invalid checkpoint: {path}") from error


@dataclass(frozen=True, slots=True)
class FrozenProtocol:
    """Target-free rows and immutable protocol provenance, before event access."""

    root: Path
    contract: dict[str, Any]
    contract_sha256: str
    manifest_sha256: str
    training_rows: tuple[dict[str, str], ...]
    split_counts: dict[str, int]

    def authorize(self, event_id: str) -> dict[str, str]:
        for row in self.training_rows:
            if row["event_id"] == event_id:
                return row
        raise ProtectedSplitError(f"Event {event_id!r} is not an authorized training event.")


def load_protocol(
    root: Path,
    contract_path: Path,
    manifest_path: Path,
    *,
    expected_contract_sha256: str = FROZEN_CONTRACT_SHA256,
) -> FrozenProtocol:
    """Verify the frozen contract and target-free manifest before any raw reads."""
    root = root.resolve()
    contract_bytes = contract_path.read_bytes()
    digest = hashlib.sha256(contract_bytes).hexdigest()
    if digest != expected_contract_sha256:
        raise CheckpointIntegrityError("The baseline contract has changed.")
    contract = json.loads(contract_bytes)
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_hash != contract["execution_manifest_sha256"]:
        raise CheckpointIntegrityError("The target-free execution manifest has changed.")
    reader = csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8")))
    if reader.fieldnames != EXECUTION_COLUMNS:
        raise ValueError("Execution manifest must contain only the four target-free columns.")
    rows = list(reader)
    if len(rows) != contract["event_count"]:
        raise ValueError("Execution manifest event count does not match the contract.")
    seen: set[str] = set()
    for row in rows:
        event_id = row["event_id"]
        if not re.fullmatch(r"[0-9]{12}", event_id) or event_id in seen:
            raise ValueError("Manifest IDs must be unique canonical twelve-digit strings.")
        seen.add(event_id)
        if row["split"] not in {"train", "validation", "test"} or row["release"] != "3":
            raise ValueError("Unsupported split or release in the execution manifest.")
        if row["path"] != f"data/raw/events/Auger_{event_id}.json" or None in row:
            raise ValueError("Event paths must be canonical, without extra CSV fields.")
    return FrozenProtocol(
        root,
        contract,
        digest,
        manifest_hash,
        tuple(row for row in rows if row["split"] == "train"),
        dict(Counter(row["split"] for row in rows)),
    )


def _source_hashes(root: Path) -> dict[str, str]:
    paths = sorted((root / "src/auger_reco").rglob("*.py"))
    paths.extend(p for p in (root / "pyproject.toml", root / "uv.lock") if p.exists())
    return {str(path.relative_to(root)): _file_hash(path) for path in paths}


def prepare_run(protocol: FrozenProtocol, run_dir: Path) -> tuple[dict[str, Any], str]:
    """Create a reproducible run, or refuse resume after source/config drift."""
    previous_path = protocol.root / "data/manifests/real_front_development_v1.json"
    previous = json.loads(previous_path.read_bytes()) if previous_path.exists() else {"events": []}
    training_ids = [row["event_id"] for row in protocol.training_rows]
    configuration = {
        "schema_version": SCHEMA_VERSION,
        "direction_frame_version": direction_reference.DIRECTION_FRAME_VERSION,
        "run_id": run_dir.name,
        "repository": str(protocol.root),
        "contract_sha256": protocol.contract_sha256,
        "execution_manifest_sha256": protocol.manifest_sha256,
        "protocol": protocol.contract,
        "training_ids": training_ids,
        "split_counts": protocol.split_counts,
        "previous_development_ids": sorted(
            e["event_id"] for e in previous["events"] if e["event_id"] in training_ids
        ),
        "source_hashes": _source_hashes(protocol.root),
        "python": platform.python_version(),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "pandas", "matplotlib", "pyproj")
        },
        "numerical_environment": {
            name: os.environ.get(name)
            for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        },
        "execution": "training_only; full and all station-LOO fits; no core-offset probes",
        "serialization_nonfinite_fields": [],
    }
    path = run_dir / "configuration.json"
    if path.exists():
        existing, digest = read_checkpoint(path)
        if existing.get("direction_frame_version") != direction_reference.DIRECTION_FRAME_VERSION:
            raise CheckpointIntegrityError(
                "Legacy or incompatible reference-direction frame. Preserve this run; "
                "use a new run directory or the saved-result coordinate audit. "
                "Existing checkpoints will not be overwritten or relabeled."
            )
        if existing != configuration:
            raise CheckpointIntegrityError("Resume source, environment, or configuration changed.")
    else:
        digest = write_checkpoint(path, configuration)
    for relative, expected_hash in configuration["source_hashes"].items():
        snapshot = run_dir / "source_snapshot" / relative
        if not snapshot.exists():
            _publish_bytes(snapshot, (protocol.root / relative).read_bytes())
        if _file_hash(snapshot) != expected_hash:
            raise CheckpointIntegrityError(f"Source snapshot mismatch: {relative}")
    events_dir = run_dir / "events"
    if events_dir.exists():
        for path in events_dir.iterdir():
            if path.is_dir():
                protocol.authorize(path.name)
    return configuration, digest


def _event_path(protocol: FrozenProtocol, event_id: str) -> Path:
    row = protocol.authorize(event_id)
    directory = protocol.root / "data/raw/events"
    path = protocol.root / row["path"]
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise CheckpointIntegrityError("Unexpected event symlink or resolved event path.")
    return path


def _check_raw(path: Path, expected: str) -> None:
    if not path.is_file() or _file_hash(path) != expected:
        raise CheckpointIntegrityError(f"Raw event changed after checkpoint: {path.name}")


def _bound_checkpoint(
    path: Path,
    *,
    event_id: str,
    configuration_sha256: str,
) -> tuple[dict[str, Any], str]:
    payload, digest = read_checkpoint(path)
    if payload.get("event_id") != event_id or payload.get("configuration_sha256") != (
        configuration_sha256
    ):
        raise CheckpointIntegrityError(f"Event/configuration binding mismatch: {path}")
    return payload, digest


def process_event(
    protocol: FrozenProtocol,
    run_dir: Path,
    event_id: str,
    configuration_sha256: str,
) -> dict[str, Any]:
    """Advance one authorized event through immutable prediction/reference gates."""
    raw_path = _event_path(protocol, event_id)  # Gate before even reading a checkpoint.
    configuration, actual_configuration_hash = read_checkpoint(run_dir / "configuration.json")
    if (
        actual_configuration_hash != configuration_sha256
        or configuration.get("direction_frame_version")
        != direction_reference.DIRECTION_FRAME_VERSION
    ):
        raise CheckpointIntegrityError(
            "Legacy or incompatible configuration frame/hash; preserve the existing run "
            "and start a new corrected run directory."
        )
    directory = run_dir / "events" / event_id
    binding = {"event_id": event_id, "configuration_sha256": configuration_sha256}
    outcome_path = directory / "outcome.json"
    receipt_path = directory / "download.json"
    prediction_path = directory / "predictions.json"
    reference_path = directory / "reference_evaluation.json"

    def read(path: Path) -> tuple[dict[str, Any], str]:
        protocol.authorize(event_id)
        return _bound_checkpoint(path, **binding)

    if not receipt_path.exists() and any(
        path.exists() for path in (prediction_path, reference_path, outcome_path)
    ):
        raise CheckpointIntegrityError("An event checkpoint lost its download receipt.")
    if reference_path.exists() and not prediction_path.exists():
        raise CheckpointIntegrityError("A reference checkpoint lost its preceding predictions.")
    if receipt_path.exists():
        receipt, receipt_hash = read(receipt_path)
    else:
        receipt = {**binding, "receipt": download_event(event_id, raw_path.parent)}
        receipt_hash = write_checkpoint(receipt_path, receipt)
        receipt, _ = read(receipt_path)
    download = receipt["receipt"]
    raw_hash = download.get("sha256")
    if raw_hash is not None:
        _check_raw(raw_path, raw_hash)

    existing_prediction_hash = None
    if prediction_path.exists():
        saved_prediction, existing_prediction_hash = read(prediction_path)
        if (
            saved_prediction["raw_sha256"] != raw_hash
            or saved_prediction["download_sha256"] != receipt_hash
        ):
            raise CheckpointIntegrityError("Prediction input/download binding changed.")
    if reference_path.exists():
        saved_reference, _ = read(reference_path)
        if saved_reference.get("direction_frame_version") != (
            direction_reference.DIRECTION_FRAME_VERSION
        ):
            raise CheckpointIntegrityError(
                "Legacy or incompatible reference checkpoint; use a new run directory "
                "or the saved-result coordinate audit."
            )
        if (
            saved_reference["raw_sha256"] != raw_hash
            or saved_reference["prediction_sha256"] != existing_prediction_hash
        ):
            raise CheckpointIntegrityError("Reference input/prediction binding changed.")
    if outcome_path.exists():
        outcome, _ = read(outcome_path)
        if outcome.get("direction_frame_version") != direction_reference.DIRECTION_FRAME_VERSION:
            raise CheckpointIntegrityError(
                "Legacy or incompatible outcome frame; use a new run directory "
                "or the saved-result coordinate audit."
            )
        if outcome["download_sha256"] != receipt_hash or outcome["raw_sha256"] != raw_hash:
            raise CheckpointIntegrityError("Outcome download binding changed.")
        for key, path in (
            ("prediction_sha256", prediction_path),
            ("reference_evaluation_sha256", reference_path),
        ):
            if outcome.get(key) is not None and read(path)[1] != outcome[key]:
                raise CheckpointIntegrityError(f"Outcome {key} binding changed.")
        return outcome

    def finish(status: str, **details: Any) -> dict[str, Any]:
        outcome = {
            **binding,
            "direction_frame_version": direction_reference.DIRECTION_FRAME_VERSION,
            "status": status,
            "raw_sha256": raw_hash,
            "download_sha256": receipt_hash,
            "reference_comparisons": [],
            "completed_at_utc": datetime.now(UTC).isoformat(),
            **details,
        }
        write_checkpoint(outcome_path, outcome)
        return read(outcome_path)[0]

    if download["status"] == "failed":
        return finish("download_failed", failure_type="DownloadError", errors=download["errors"])
    if not isinstance(raw_hash, str):
        raise CheckpointIntegrityError("Successful download has no raw content hash.")

    if prediction_path.exists():
        prediction, prediction_hash = read(prediction_path)
        if prediction["raw_sha256"] != raw_hash:
            raise CheckpointIntegrityError("Prediction/raw binding changed.")
    else:
        try:
            fit_input = event_json.load_auger_plane_front_input(raw_path, minimum_stations=6)
            core = core_reference.load_auger_core_reference(raw_path)
            if fit_input.canonical_event_id != event_id or (
                core.event_id,
                core.embedded_release,
                core.format_version,
            ) != (fit_input.event_id, fit_input.embedded_release, fit_input.format_version):
                raise CheckpointIntegrityError("Core and station event metadata disagree.")
        except event_json.AugerEventDataError as error:
            _check_raw(raw_path, raw_hash)
            return finish(
                "input_failed", failure_type=type(error).__name__, failure_message=str(error)
            )
        _check_raw(raw_path, raw_hash)
        options = dict(protocol.contract["quadratic_options"])
        options["positive_curvature_seeds_ns"] = tuple(options["positive_curvature_seeds_ns"])
        result = compare_event_fronts(
            fit_input.station_positions_m,
            fit_input.observed_times_ns,
            fit_input.timing_uncertainties_ns,
            core.position_m,
            station_ids=fit_input.station_ids,
            plane_options=PlaneFrontFitOptions(**protocol.contract["plane_options"]),
            curved_options=QuadraticFrontFitOptions(**options),
            core_offsets_m=np.empty((0, 3)),
            run_leave_one_out=True,
        )
        if len(result.records) != 4 + 4 * fit_input.number_of_stations:
            raise RuntimeError("Comparison did not retain every planned full/LOO fit.")
        prediction = {
            **binding,
            "raw_sha256": raw_hash,
            "download_sha256": receipt_hash,
            "event_metadata": {
                "number_of_stations": fit_input.number_of_stations,
                "embedded_release": fit_input.embedded_release,
                "format_version": fit_input.format_version,
                "input_quality_flags": fit_input.quality_flags,
                "selection_policy": fit_input.selection_policy,
            },
            "inputs": {
                "station_ids": fit_input.station_ids,
                "positions_m": fit_input.station_positions_m,
                "observed_times_ns": fit_input.observed_times_ns,
                "uncertainties_ns": fit_input.timing_uncertainties_ns,
                "published_core_position_m": core.position_m,
            },
            "records": [{**row, "event_id": event_id} for row in result.records],
            "optimizer_attempts": result.optimizer_attempts,
            "station_residuals": result.station_residuals,
            "fit_configuration": result.configuration,
        }
        _check_raw(raw_path, raw_hash)
        prediction_hash = write_checkpoint(prediction_path, prediction)
        prediction, verified_hash = read(prediction_path)
        if verified_hash != prediction_hash:
            raise CheckpointIntegrityError("Prediction publication failed verification.")

    # No published direction was consumed above. This barrier also holds on resume.
    _check_raw(raw_path, raw_hash)
    if reference_path.exists():
        evaluation, evaluation_hash = read(reference_path)
        if evaluation["prediction_sha256"] != prediction_hash:
            raise CheckpointIntegrityError("Reference/prediction binding changed.")
    else:
        try:
            site_reference = direction_reference.load_auger_site_direction_reference(raw_path)
            reference = site_reference.reference
            metadata = prediction["event_metadata"]
            if reference.canonical_event_id != event_id or (
                reference.embedded_release,
                reference.format_version,
            ) != (metadata["embedded_release"], metadata["format_version"]):
                raise CheckpointIntegrityError("Reference metadata disagrees with predictions.")
            sky = site_reference.sky_direction_site
            comparisons = [
                {
                    "model": row["model"],
                    "weighting": row["weighting"],
                    "direction_frame_version": direction_reference.DIRECTION_FRAME_VERSION,
                    "separation_from_auger_deg": angular_separation_deg(
                        np.array([row["sky_x"], row["sky_y"], row["sky_z"]]), sky
                    ),
                }
                for row in prediction["records"]
                if row["stage"] == "full" and row["success"]
            ]
            evaluation = {
                **binding,
                "direction_frame_version": direction_reference.DIRECTION_FRAME_VERSION,
                "direction_frame_metadata": site_reference.frame_metadata,
                "reference_sky_direction_site": sky,
                "raw_sha256": raw_hash,
                "prediction_sha256": prediction_hash,
                "reference": asdict(reference),
                "reference_comparisons": comparisons,
            }
        except event_json.AugerEventDataError as error:
            _check_raw(raw_path, raw_hash)
            return finish(
                "reference_failed",
                prediction_sha256=prediction_hash,
                failure_type=type(error).__name__,
                failure_message=str(error),
            )
        _check_raw(raw_path, raw_hash)
        evaluation_hash = write_checkpoint(reference_path, evaluation)
        evaluation, _ = read(reference_path)
    records = prediction["records"]
    return finish(
        "complete",
        prediction_sha256=prediction_hash,
        reference_evaluation_sha256=evaluation_hash,
        reference_comparisons=evaluation["reference_comparisons"],
        fit_attempt_count=len(records),
        successful_fit_count=sum(r["success"] for r in records),
        fit_failure_counts=dict(Counter(r["failure_type"] for r in records if not r["success"])),
    )


def run_batch(
    protocol: FrozenProtocol,
    run_dir: Path,
    *,
    workers: int = 2,
    max_events: int | None = None,
) -> dict[str, Any]:
    """Run a bounded prefix of pending training events, under a single-writer lock.

    ``max_events`` limits this invocation, not the scientific population. Resume
    with it omitted to finish all training events. Threading overlaps bounded
    downloads; two workers avoid aggressively querying the public data server.
    """
    import fcntl

    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 4:
        raise ValueError("workers must be an integer from one to four.")
    if max_events is not None and (
        isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1
    ):
        raise ValueError("max_events must be a positive integer or None.")
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / ".writer.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another process is already writing this run.") from error
        configuration, config_hash = prepare_run(protocol, run_dir)
        completed: list[dict[str, Any]] = []
        pending: list[str] = []
        for event_id in configuration["training_ids"]:
            protocol.authorize(event_id)
            if (run_dir / "events" / event_id / "outcome.json").exists():
                completed.append(process_event(protocol, run_dir, event_id, config_hash))
            else:
                pending.append(event_id)
        selected = pending if max_events is None else pending[:max_events]
        print(
            f"Training: {len(completed)} terminal, {len(selected)} scheduled, "
            f"{len(configuration['training_ids'])} total; protected events excluded.",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_event, protocol, run_dir, event_id, config_hash): event_id
                for event_id in selected
            }
            try:
                for future in as_completed(futures):
                    outcome = future.result()  # Unexpected/programming failures abort loudly.
                    completed.append(outcome)
                    if len(completed) % 10 == 0 or len(selected) <= 2:
                        print(
                            f"Terminal events: {len(completed)}; latest "
                            f"{outcome['event_id']}: {outcome['status']}",
                            flush=True,
                        )
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
        if _source_hashes(protocol.root) != configuration["source_hashes"]:
            raise CheckpointIntegrityError(
                "Source changed during execution; do not report this run."
            )
        receipt = {
            "configuration_sha256": config_hash,
            "training_total": len(configuration["training_ids"]),
            "terminal_events": len(completed),
            "statuses": dict(Counter(row["status"] for row in completed)),
            "protected_events_accessed": 0,
            "finished_at_utc": datetime.now(UTC).isoformat(),
        }
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
        write_checkpoint(run_dir / "invocations" / f"{stamp}.json", receipt)
        return receipt


def main() -> None:
    """Run or resume the frozen training comparison, then rebuild derived reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-events", type=int)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    protocol = load_protocol(
        root,
        root / HANDOFF / "pilot_baseline_contract.json",
        root / HANDOFF / "pilot_execution_target_free.csv",
    )
    receipt = run_batch(
        protocol, arguments.run_dir, workers=arguments.workers, max_events=arguments.max_events
    )
    print(json.dumps(receipt, indent=2), flush=True)
    from auger_reco.evaluation.pilot_reporting import build_report

    build_report(arguments.run_dir.resolve())


if __name__ == "__main__":
    main()
