"""Freeze a training-only development sample before accessing fit outcomes.

This is an intentionally stratified convenience sample, not a population estimate.
Requiring seven selected stations lets leave-one-station-out fits retain six.
Reference angles, energy, and validation/test outcomes never enter selection.
"""

from __future__ import annotations

import csv
import hashlib
import http.client
import json
import math
import os
import tempfile
import urllib.error
import urllib.request
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SELECTION_FIELDS = ("event_id", "split", "selected_stations", "zenith_bin", "multiplicity_bin")
DEFAULT_SEED = 20261010
MAX_EVENT_BYTES = 20 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_ATTEMPTS = 2
EVENT_URL_TEMPLATE = "https://opendata.auger.org/releases/3/data/dataSD1500/Auger_{event_id}.json"


def canonical_event_id(value: object) -> str:
    """Normalize a nonnegative, at-most-twelve-digit event identifier."""
    if isinstance(value, bool):
        raise ValueError("An event identifier cannot be a boolean.")
    text = str(value).strip()
    if not text.isascii() or not text.isdigit() or len(text) > 12:
        raise ValueError(f"Invalid event identifier: {value!r}.")
    return f"{int(text):012d}"


def load_selection_rows(path: Path) -> list[dict[str, str]]:
    """Project CSV rows onto the five permitted sampling fields only."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not set(SELECTION_FIELDS).issubset(reader.fieldnames or ()):
            raise ValueError("The cohort is missing required selection fields.")
        return [{key: row[key] for key in SELECTION_FIELDS} for row in reader]


def select_development_events(
    rows: Iterable[Mapping[str, object]],
    *,
    count: int = 19,
    seed: int = DEFAULT_SEED,
    minimum_stations: int = 7,
    excluded_event_ids: Iterable[object] = ("081847956000",),
) -> list[dict[str, object]]:
    """Choose fixed hash-ordered round-robin strata, independent of input order.

    Only training rows are eligible. Strata are lexicographically ordered pairs
    ``(zenith_bin, multiplicity_bin)``. Within each stratum the ascending key is
    SHA256 of UTF-8 ``'{seed}:{canonical_event_id}'``, with event ID tie-breaking.
    No replacement is permitted when a subsequently downloaded event fails.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer.")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer.")
    if (
        isinstance(minimum_stations, bool)
        or not isinstance(minimum_stations, int)
        or minimum_stations < 7
    ):
        raise ValueError("minimum_stations must be an integer at least seven.")
    excluded = {canonical_event_id(value) for value in excluded_event_ids}
    strata: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        # Do not even inspect counts or bins on validation/test rows.
        if row.get("split") != "train":
            continue
        event_id = canonical_event_id(row["event_id"])
        if event_id in seen:
            raise ValueError(f"Duplicate training event identifier: {event_id}.")
        seen.add(event_id)
        if event_id in excluded:
            continue
        raw_count = row["selected_stations"]
        if isinstance(raw_count, bool):
            raise ValueError("Station counts cannot be booleans.")
        station_count = float(raw_count)
        if not math.isfinite(station_count) or station_count < 0 or not station_count.is_integer():
            raise ValueError(f"Invalid station count for event {event_id}.")
        if station_count < minimum_stations:
            continue
        bins = (str(row["zenith_bin"]).strip(), str(row["multiplicity_bin"]).strip())
        if not all(bins):
            raise ValueError(f"Empty sampling stratum for event {event_id}.")
        strata[bins].append(
            {
                "event_id": event_id,
                "split": "train",
                "selected_stations": int(station_count),
                "zenith_bin": bins[0],
                "multiplicity_bin": bins[1],
            }
        )
    if sum(map(len, strata.values())) < count:
        raise ValueError("Not enough eligible training events; no sample was selected.")

    def ordering(row: dict[str, object]) -> tuple[str, str]:
        event_id = str(row["event_id"])
        digest = hashlib.sha256(f"{seed}:{event_id}".encode()).hexdigest()
        return digest, event_id

    queues = [deque(sorted(strata[key], key=ordering)) for key in sorted(strata)]
    selected: list[dict[str, object]] = []
    while len(selected) < count:
        for queue in queues:
            if queue and len(selected) < count:
                selected.append(queue.popleft())
    return selected


def _validate_event_bytes(payload: bytes, event_id: str) -> None:
    """Check the bounded payload and event identity without consuming targets."""
    if not payload or len(payload) > MAX_EVENT_BYTES:
        raise ValueError("Event payload is empty or exceeds the 20 MiB safety limit.")
    try:
        document = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Event payload is not a valid JSON document.") from error
    if not isinstance(document, dict) or not isinstance(document.get("info"), dict):
        raise ValueError("Event payload must be a JSON object containing info.")
    if canonical_event_id(document["info"].get("id")) != event_id:
        raise ValueError("Downloaded event identity does not match the frozen selection.")


def _read_bounded(handle: Any) -> bytes:
    payload = handle.read(MAX_EVENT_BYTES + 1)
    if len(payload) > MAX_EVENT_BYTES:
        raise ValueError("Download exceeds the 20 MiB safety limit.")
    return payload


def _publish_new_file(destination: Path, payload: bytes) -> None:
    """Atomically publish a complete file, failing rather than replacing a file.

    A same-directory temporary file is linked only after flush/fsync. Unlike
    ``os.replace``, linking fails atomically if another writer created the target.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".auger-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def download_event(event_id: str, directory: Path) -> dict[str, object]:
    """Download one frozen event, keeping bounded failure details and existing files."""
    event_id = canonical_event_id(event_id)
    destination = directory / f"Auger_{event_id}.json"
    url = EVENT_URL_TEMPLATE.format(event_id=event_id)
    record: dict[str, object] = {"event_id": event_id, "url": url, "path": str(destination)}
    errors: list[dict[str, object]] = []
    if destination.exists():
        try:
            with destination.open("rb") as handle:
                payload = _read_bounded(handle)
            _validate_event_bytes(payload, event_id)
        except (OSError, ValueError) as error:
            return {**record, "status": "failed", "attempts": 0, "errors": [str(error)]}
        return {
            **record,
            "status": "already_present",
            "attempts": 0,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "auger-direction-reconstruction/0.1 (research development sample)"
                },
            )
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                final_url = response.geturl()
                if not final_url.startswith("https://opendata.auger.org/"):
                    raise ValueError("Download redirected outside the official HTTPS portal.")
                payload = _read_bounded(response)
            _validate_event_bytes(payload, event_id)
            _publish_new_file(destination, payload)
            return {
                **record,
                "status": "downloaded",
                "attempts": attempt,
                "errors": errors,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
            errors.append({"attempt": attempt, "type": type(error).__name__, "message": str(error)})
    return {**record, "status": "failed", "attempts": MAX_DOWNLOAD_ATTEMPTS, "errors": errors}


def download_development_manifest(
    manifest_path: Path, event_directory: Path, receipt_path: Path
) -> dict[str, object]:
    """Download only the already frozen identities and create a separate receipt.

    Failed files remain failed entries, never replacements. Existing receipts
    are not overwritten; use a new receipt path when intentionally retrying.
    """
    if receipt_path.exists():
        raise FileExistsError(f"Download receipt already exists: {receipt_path}.")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("status") != "frozen_before_download_and_fit":
        raise ValueError("Downloads require a frozen development manifest.")
    events = manifest.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("Frozen manifest has no event list.")
    event_ids = [canonical_event_id(event["event_id"]) for event in events]
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Frozen manifest contains duplicate identities.")
    receipt: dict[str, object] = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "selection_manifest": str(manifest_path),
        "selection_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "no_replacement_policy": True,
        "records": [download_event(event_id, event_directory) for event_id in event_ids],
    }
    _publish_new_file(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    return receipt
