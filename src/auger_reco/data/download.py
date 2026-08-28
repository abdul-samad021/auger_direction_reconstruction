from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from auger_reco.data.sources import PROJECT_ROOT, DataSource, load_sources

CHUNK_BYTES = 1024 * 1024
USER_AGENT = "auger-direction-reconstruction/0.1 (undergraduate research project)"


def _hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_and_hash(source: BinaryIO, destination: BinaryIO) -> tuple[str, str, int]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    total = 0
    while chunk := source.read(CHUNK_BYTES):
        destination.write(chunk)
        md5.update(chunk)
        sha256.update(chunk)
        total += len(chunk)
    return md5.hexdigest(), sha256.hexdigest(), total


def _existing_result(source: DataSource, destination: Path) -> dict[str, object]:
    size = destination.stat().st_size
    md5 = _hash_file(destination, "md5")
    if source.expected_bytes and size != source.expected_bytes:
        raise ValueError(f"Existing file has {size} bytes; expected {source.expected_bytes}.")
    if source.expected_md5 and md5 != source.expected_md5:
        raise ValueError(f"Existing file MD5 {md5} does not match {source.expected_md5}.")
    return {
        "status": "already-present",
        "source": source.name,
        "path": str(destination.relative_to(PROJECT_ROOT)),
        "bytes": size,
        "md5": md5,
        "sha256": _hash_file(destination, "sha256"),
    }


def _append_manifest(record: dict[str, object]) -> None:
    manifest = PROJECT_ROOT / "data" / "manifests" / "downloads.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def download_source(name: str, *, allow_large: bool = False) -> dict[str, object]:
    sources = load_sources()
    if name not in sources:
        choices = ", ".join(sorted(sources))
        raise ValueError(f"Unknown source {name!r}. Choose one of: {choices}.")

    source = sources[name]
    if source.large and not allow_large:
        raise ValueError(
            f"{name!r} is marked large. Re-run with --allow-large after pilot validation."
        )

    destination = PROJECT_ROOT / source.relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return _existing_result(source, destination)

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            with temporary.open("wb") as output:
                md5, sha256, size = _copy_and_hash(response, output)

        if source.expected_bytes and size != source.expected_bytes:
            raise ValueError(f"Downloaded {size} bytes; expected {source.expected_bytes}.")
        if source.expected_md5 and md5 != source.expected_md5:
            raise ValueError(f"Downloaded MD5 {md5} does not match {source.expected_md5}.")

        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    record: dict[str, object] = {
        "status": "downloaded",
        "downloaded_at": datetime.now(UTC).isoformat(),
        "source": source.name,
        "url": source.url,
        "path": str(destination.relative_to(PROJECT_ROOT)),
        "bytes": size,
        "md5": md5,
        "sha256": sha256,
    }
    _append_manifest(record)
    return record
