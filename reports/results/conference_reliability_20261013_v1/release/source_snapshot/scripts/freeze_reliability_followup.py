"""Seal the separate directional-reliability follow-up without Git mutations.

The original conference release remains immutable. This seal records source
versions, numerical replay receipts and quality gates; it is not a claim that
the tested uncertainty estimates or warning policy are scientifically adequate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("reports/results/conference_reliability_20261013_v1")
SOURCE_NAMES = (
    "docs/reliability_followup_protocol.md",
    "docs/direction_uncertainty_protocol.md",
    "docs/reliability_warning_protocol.md",
    "docs/reliability_followup_guide.md",
    "reports/direction_uncertainty_conclusion.md",
    "reports/reliability_warning_conclusion.md",
    "reports/reliability_followup_conclusion.md",
    "src/auger_reco/evaluation/direction_uncertainty.py",
    "src/auger_reco/evaluation/reliability_warning.py",
    "scripts/audit_reliability_followup.py",
    "scripts/complete_direction_uncertainty_report.py",
    "scripts/freeze_reliability_followup.py",
    "tests/test_direction_uncertainty.py",
    "tests/test_reliability_warning.py",
    "tests/test_reliability_followup.py",
    "tests/test_reliability_release.py",
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_command(root, arguments):
    environment = dict(
        os.environ,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        MPLBACKEND="Agg",
    )
    completed = subprocess.run(
        arguments, cwd=root, env=environment, capture_output=True, text=True, check=False
    )
    return {
        "arguments": arguments,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def original_seal(root):
    receipt = run_command(
        root, [str(root / ".venv/bin/python"), "scripts/freeze_conference_release.py", "verify"]
    )
    if receipt["returncode"] != 0:
        raise RuntimeError("Original conference verification failed to run.")
    result = json.loads(receipt["stdout"])
    if not result["passed"]:
        raise RuntimeError("Original conference evidence changed.")
    return result


def only_plot_changed(before, after):
    """Allow a documented plotting-only repair, not changed scientific functions."""
    left, right = ast.parse(before), ast.parse(after)
    for tree in (left, right):
        tree.body = [
            item
            for item in tree.body
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            or item.name != "_figures"
        ]
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def source_versions(root):
    """Check the actual versions used by each study against live/source snapshots."""
    base = root / BASE
    config_a = json.loads((base / "stage_a/final_v2/protocol_lock.json").read_text())
    config_b = json.loads((base / "stage_b/configuration.json").read_text())
    checks = []
    for relative, checksum in config_a["sources"].items():
        snapshot = base / "stage_a/final_v2/source_snapshot" / relative
        if digest(snapshot) != checksum or digest(root / relative) != checksum:
            raise ValueError(f"Stage A scientific source changed: {relative}")
        checks.append({"stage": "A", "source": relative, "live_matches": True})
    for item in config_b["sources"]:
        relative, checksum = item["path"], item["sha256"]
        snapshot = base / "stage_b/source_snapshot" / Path(relative).name
        if digest(snapshot) != checksum:
            raise ValueError(f"Stage B source snapshot changed: {relative}")
        matches = digest(root / relative) == checksum
        plot_only = False
        if not matches and relative == "src/auger_reco/evaluation/direction_uncertainty.py":
            plot_only = only_plot_changed(snapshot.read_text(), (root / relative).read_text())
        if not matches and not plot_only:
            raise ValueError(f"Unapproved Stage B source change: {relative}")
        checks.append(
            {
                "stage": "B",
                "source": relative,
                "live_matches": matches,
                "plot_only_amendment": plot_only,
            }
        )
    return checks


def files(directory):
    result = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink: {path}")
        if path.is_file() and "__pycache__" not in path.parts:
            result.append(path)
    return result


def freeze(root):
    base = root / BASE
    destination = base / "release"
    if destination.exists():
        raise FileExistsError("The follow-up release already exists; do not overwrite it.")
    for relative in SOURCE_NAMES:
        if not (root / relative).is_file():
            raise FileNotFoundError(relative)
    evidence = json.loads((base / "independent_audit.json").read_text())
    if (
        not evidence["passed"]
        or evidence["audit_source_sha256"] != digest(root / "scripts/audit_reliability_followup.py")
        or evidence["stage_a"]["attempted_fits"] != 4800
        or evidence["stage_a"]["manifest_sha256"] != digest(base / "stage_a/final_v2/manifest.json")
        or evidence["stage_b"]["manifest_sha256"] != digest(base / "stage_b/manifest.json")
        or sum(p["records"] for p in evidence["stage_b"]["phases"].values()) != 7200
    ):
        raise ValueError("Independent replay receipt is incomplete or stale.")
    baseline = original_seal(root)
    versions = source_versions(root)
    before = {relative: digest(root / relative) for relative in SOURCE_NAMES}
    python, ruff = str(root / ".venv/bin/python"), str(root / ".venv/bin/ruff")
    checks = {
        "tests_warnings_as_errors": run_command(root, [python, "-m", "pytest", "-W", "error"]),
        "all_python_lint": run_command(root, [ruff, "check", "src", "tests", "scripts"]),
        "new_python_format": run_command(
            root, [ruff, "format", "--check", *[p for p in SOURCE_NAMES if p.endswith(".py")]]
        ),
    }
    if any(item["returncode"] for item in checks.values()):
        raise RuntimeError(json.dumps(checks, indent=2))
    if before != {relative: digest(root / relative) for relative in SOURCE_NAMES}:
        raise RuntimeError("Source changed while quality gates ran.")
    destination.mkdir()
    for relative in SOURCE_NAMES:
        target = destination / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    validation = {"quality_gates": checks, "original_seal": baseline, "source_versions": versions}
    (destination / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    artifact_map = {str(path.relative_to(root)): digest(path) for path in files(base)}
    artifact_map.update(before)
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "original_manifest_sha256": baseline["manifest_sha256"],
        "canonical_stage_a": str(BASE / "stage_a/final_v2"),
        "canonical_stage_b": str(BASE / "stage_b"),
        "artifact_sha256": artifact_map,
        "interpretation": "Evidence integrity, not promotion of a detector-calibrated method.",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return verify(root)


def verify(root):
    base = root / BASE
    manifest_path = base / "release/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changed = [
        relative
        for relative, checksum in manifest["artifact_sha256"].items()
        if not (root / relative).is_file() or digest(root / relative) != checksum
    ]
    unexpected = [
        str(path.relative_to(root))
        for path in files(base)
        if path != manifest_path and str(path.relative_to(root)) not in manifest["artifact_sha256"]
    ]
    original = original_seal(root)
    return {
        "passed": not changed and not unexpected and original["passed"],
        "checked_artifacts": len(manifest["artifact_sha256"]),
        "changed_or_missing": changed,
        "unexpected": unexpected,
        "manifest_sha256": digest(manifest_path),
        "original_seal": original,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "verify"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = (freeze if args.mode == "freeze" else verify)(root)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
