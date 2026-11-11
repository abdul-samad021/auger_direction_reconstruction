"""Preserve and verify the pre-conference working evidence without Git writes.

The original result files are hashed in place, while source, tests, documents
and notebooks are additionally copied. Newly named conference work is excluded
so independent investigators can work in parallel. No raw event is parsed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    """Hash bytes in bounded memory, including large saved result arrays."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def original_paths(repository: Path) -> list[Path]:
    """Inventory non-ignored originals, excluding caches and this new study."""
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repository,
    )
    result = []
    for relative in sorted(set(raw.decode().split("\0")) - {""}):
        path = Path(relative)
        if any("conference_" in part for part in path.parts):
            continue
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
            continue
        absolute = repository / path
        if absolute.is_symlink() or not absolute.resolve().is_relative_to(repository.resolve()):
            raise ValueError(f"Unexpected nonlocal baseline path: {path}")
        if absolute.is_file():
            result.append(path)
    return result


def preserve(repository: Path, output: Path) -> dict:
    """Create a new, exclusive preservation receipt; never refresh a baseline."""
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for path in original_paths(repository):
        absolute = repository / path
        files[path.as_posix()] = {"sha256": digest(absolute), "bytes": absolute.stat().st_size}
        if not path.as_posix().startswith("reports/results/"):
            target = output / "source_snapshot" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(absolute, target)
            if digest(target) != files[path.as_posix()]["sha256"]:
                raise RuntimeError(f"Snapshot mismatch: {path}")
    document = {
        "created_utc": datetime.now(UTC).isoformat(),
        "repository": str(repository.resolve()),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository)
        .decode()
        .strip(),
        "git_status": subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=repository
        ).decode(),
        "files": files,
        "original_tests": sorted(
            p for p in files if p.startswith("tests/test_") and p.endswith(".py")
        ),
        "raw_event_filenames": sorted(
            p.name for p in (repository / "data/raw/events").glob("*.json")
        ),
        "note": "No raw event content was opened by this preservation operation.",
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return {"files": len(files), "bytes": sum(r["bytes"] for r in files.values())}


def verify(repository: Path, output: Path) -> dict:
    """Detect any removed/changed baseline evidence and unexpected raw additions."""
    document = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    changes = []
    snapshot_changes = []
    for relative, expected in document["files"].items():
        path = repository / relative
        if not path.is_file() or digest(path) != expected["sha256"]:
            changes.append(relative)
        copy = output / "source_snapshot" / relative
        if not relative.startswith("reports/results/") and (
            not copy.is_file() or digest(copy) != expected["sha256"]
        ):
            snapshot_changes.append(relative)
    raw_now = sorted(p.name for p in (repository / "data/raw/events").glob("*.json"))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository).decode().strip()
    return {
        "checked_files": len(document["files"]),
        "changed_originals": changes,
        "changed_snapshot_files": snapshot_changes,
        "raw_event_inventory_unchanged": raw_now == document["raw_event_filenames"],
        "git_head_unchanged": head == document["head"],
        "passed": not changes
        and not snapshot_changes
        and raw_now == document["raw_event_filenames"]
        and head == document["head"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preserve", "verify"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (preserve if args.operation == "preserve" else verify)(
        args.repository.resolve(), args.output.resolve()
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    if result.get("passed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
