"""Validate and seal a new conference evidence package without any Git writes.

The manifest detects changes; it is not a claim of physical correctness. Historical
result directories remain in place and are covered by the preserved baseline hash
inventory. Freeze refuses to overwrite a release, including a failed gate receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT_RELATIVE = Path("reports/results/conference_validation_20261013_v1")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def new_source_paths(root: Path) -> list[Path]:
    """Select only this research addition; do not copy personal/external files."""
    patterns = (
        "docs/conference_*.md",
        "reports/conference_*.md",
        "scripts/*conference*.py",
        "src/auger_reco/evaluation/conference_*.py",
        "tests/test_conference_*.py",
        "notebooks/*conference*.ipynb",
    )
    return sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})


def checked_files(directory: Path) -> list[Path]:
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink not permitted in a frozen artifact tree: {path}")
        if path.is_file() and "__pycache__" not in path.parts:
            files.append(path)
    return files


def command(root: Path, arguments: list[str]) -> dict:
    environment = dict(
        os.environ,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        MPLBACKEND="Agg",
    )
    result = subprocess.run(
        arguments, cwd=root, env=environment, text=True, capture_output=True, check=False
    )
    return {
        "command": arguments,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def baseline_check(root: Path) -> dict:
    result = command(
        root,
        [
            str(root / ".venv/bin/python"),
            "scripts/preserve_conference_baseline.py",
            "verify",
            "--output",
            str(root / ROOT_RELATIVE / "baseline"),
        ],
    )
    if result["returncode"] != 0:
        return {"passed": False, "command_result": result}
    return json.loads(result["stdout"])


def verify_hash_map(directory: Path, mapping: dict[str, str]) -> int:
    """Verify a subordinate receipt without allowing paths to escape its directory."""
    if not mapping:
        raise ValueError("Empty artifact receipt.")
    base = directory.resolve()
    for relative, checksum in mapping.items():
        path = directory / relative
        if (
            Path(relative).is_absolute()
            or not path.resolve().is_relative_to(base)
            or path.is_symlink()
            or not path.is_file()
            or digest(path) != checksum
        ):
            raise ValueError(f"Subordinate artifact checksum/path mismatch: {relative}")
    return len(mapping)


def check_evidence_chain(directory: Path) -> dict:
    """Recheck experiment receipts, not merely hash their present contents anew."""
    receipts = (
        ("coordinates/audit_v1", "artifact_sha256.json", None),
        ("instability", "completion.json", "artifact_hashes"),
        ("instability/anchor_ablation", "completion.json", "artifacts"),
        ("stress/final", "artifact_hashes.json", None),
    )
    counts = {}
    for folder, filename, key in receipts:
        receipt = json.loads((directory / folder / filename).read_text())
        counts[folder] = verify_hash_map(
            directory / folder, receipt if key is None else receipt[key]
        )
    independent = json.loads((directory / "stress/independent_audit.json").read_text())
    if (
        independent["status"] != "passed"
        or independent["audited_fit_count"] != 28800
        or independent["audit_source_sha256"]
        != digest(directory / "stress/audit_stress_results.py")
    ):
        raise ValueError("Independent stress audit receipt is missing, invalid or stale.")
    synthesis_dir = directory / "synthesis_v2"
    synthesis = json.loads((synthesis_dir / "summary.json").read_text())
    for key, filename in (
        ("input_sha256", "input_event_metrics.csv"),
        ("source_sha256", "source_snapshot.py"),
        ("training_configuration_sha256", "training_configuration.json"),
    ):
        if synthesis[key] != digest(synthesis_dir / filename):
            raise ValueError("Synthesis snapshot checksum mismatch.")
    return {"passed": True, "verified_experiment_artifact_counts": counts}


def verify(root: Path) -> dict:
    directory = root / ROOT_RELATIVE
    manifest_path = directory / "release/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changed = [
        relative
        for relative, checksum in manifest["artifact_sha256"].items()
        if not (root / relative).is_file() or digest(root / relative) != checksum
    ]
    unexpected = sorted(
        str(path.relative_to(root))
        for path in checked_files(directory)
        if path != manifest_path and str(path.relative_to(root)) not in manifest["artifact_sha256"]
    )
    head = command(root, ["git", "rev-parse", "HEAD"])
    baseline = baseline_check(root)
    return {
        "passed": not changed
        and not unexpected
        and baseline["passed"]
        and head["returncode"] == 0
        and head["stdout"].strip() == manifest["git_head"],
        "checked_artifacts": len(manifest["artifact_sha256"]),
        "changed_or_missing": changed,
        "unexpected_artifacts": unexpected,
        "git_head_unchanged": head["stdout"].strip() == manifest["git_head"],
        "manifest_sha256": digest(manifest_path),
        "historical_baseline": baseline,
    }


def freeze(root: Path) -> dict:
    directory = root / ROOT_RELATIVE
    destination = directory / "release"
    if destination.exists():
        raise FileExistsError("Release destination already exists; preserve it.")
    required = (
        "baseline/independent_audit_20261013.json",
        "coordinates/audit_v1/summary.json",
        "instability/completion.json",
        "instability/anchor_ablation/completion.json",
        "instability/anchor_ablation/tail_numerical_audit.json",
        "stress/final/summary.json",
        "stress/independent_audit.json",
        "synthesis_v2/summary.json",
    )
    for relative in required:
        if not (directory / relative).is_file():
            raise FileNotFoundError(relative)
    for relative in (
        "reports/conference_research_conclusion.md",
        "reports/conference_instability_conclusion.md",
        "reports/conference_stress_conclusion.md",
        "docs/conference_release_guide.md",
        "docs/conference_claim_ledger.md",
    ):
        if not (root / relative).is_file():
            raise FileNotFoundError(relative)
    stress = json.loads((directory / "stress/final/summary.json").read_text())
    if (
        stress["requested_fits"] != 28800
        or stress["control_fits"] != 96
        or stress["successful_fits"] + stress["failed_fits"] != 28800
        or stress["nested_violations"] != 0
    ):
        raise ValueError("Stress run incomplete or failed its nesting gate.")
    synthesis = json.loads((directory / "synthesis_v2/summary.json").read_text())
    if synthesis["event_count"] != 711:
        raise ValueError("Unexpected training population.")
    evidence_chain = check_evidence_chain(directory)
    destination.mkdir()
    sources = new_source_paths(root)
    for path in sources:
        if path.is_symlink():
            raise ValueError("Refusing symlink source.")
        target = destination / "source_snapshot" / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    python = str(root / ".venv/bin/python")
    ruff = str(root / ".venv/bin/ruff")
    format_paths = [str(p.relative_to(root)) for p in sources if p.suffix == ".py"]
    checks = {
        "tests_warnings_as_errors": command(root, [python, "-m", "pytest", "-W", "error"]),
        "lint": command(root, [ruff, "check", "src", "tests", "scripts"]),
        "new_source_format": command(root, [ruff, "format", "--check", *format_paths]),
        "git_whitespace": command(root, ["git", "diff", "--check"]),
        "baseline_preserved": command(
            root,
            [
                python,
                "scripts/preserve_conference_baseline.py",
                "verify",
                "--output",
                str(directory / "baseline"),
            ],
        ),
    }
    # Existing test_event_json.py has two pre-existing formatting-only differences.
    # Audit them, but do not rewrite an original source merely to hide this notice.
    advisory = command(root, [ruff, "format", "--check", "src", "tests", "scripts"])
    changed_sources = [
        str(path.relative_to(root))
        for path in sources
        if digest(path) != digest(destination / "source_snapshot" / path.relative_to(root))
    ]
    passed = all(value["returncode"] == 0 for value in checks.values()) and not changed_sources
    receipt = {
        "created_utc": datetime.now(UTC).isoformat(),
        "passed": passed,
        "checks": checks,
        "historical_format_advisory": advisory,
        "evidence_chain": evidence_chain,
        "source_changes_during_validation": changed_sources,
        "no_git_writes": True,
        "protected_raw_event_contents_read": 0,
    }
    (destination / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not passed:
        raise RuntimeError("Release gates failed; inspect the preserved validation receipt.")
    artifacts = checked_files(directory) + sources
    head = command(root, ["git", "rev-parse", "HEAD"])
    status = command(root, ["git", "status", "--short"])
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "git_head": head["stdout"].strip(),
        "git_status": status["stdout"],
        "release_type": "uncommitted_conference_research",
        "historical_baseline_manifest": str(
            (directory / "baseline/manifest.json").relative_to(root)
        ),
        "canonical_synthesis": "synthesis_v2",
        "canonical_stress": "stress/final",
        "superseded_exploratory_outputs": ["synthesis_v1", "stress/smoke", "stress/full"],
        "artifact_sha256": {str(path.relative_to(root)): digest(path) for path in artifacts},
        "limitations": [
            "training-only",
            "published-core-assisted real quadratic fits",
            "toy simulations, not detector Monte Carlo",
            "no accuracy claim on real truth",
            "historical formatting-only advisory retained",
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return verify(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("freeze", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    result = (freeze if arguments.operation == "freeze" else verify)(arguments.root.resolve())
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
