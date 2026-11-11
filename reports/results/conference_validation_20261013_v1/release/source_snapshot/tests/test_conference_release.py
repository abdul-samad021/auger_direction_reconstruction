"""Release integrity checks do not execute fitting, access protected events or write Git."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/freeze_conference_release.py"
SPEC = importlib.util.spec_from_file_location("freeze_conference_release", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_missing_evidence_fails_before_creating_release(tmp_path):
    with pytest.raises(FileNotFoundError):
        release.freeze(tmp_path)
    assert not (tmp_path / release.ROOT_RELATIVE / "release").exists()


def test_existing_release_is_never_overwritten(tmp_path):
    directory = tmp_path / release.ROOT_RELATIVE / "release"
    directory.mkdir(parents=True)
    sentinel = directory / "validation.json"
    sentinel.write_text("original")
    with pytest.raises(FileExistsError):
        release.freeze(tmp_path)
    assert sentinel.read_text() == "original"


def _manifest(tmp_path, monkeypatch):
    directory = tmp_path / release.ROOT_RELATIVE
    (directory / "release").mkdir(parents=True)
    artifact = directory / "sample.json"
    artifact.write_text("original evidence")
    manifest = {
        "git_head": "abc",
        "artifact_sha256": {str(artifact.relative_to(tmp_path)): release.digest(artifact)},
    }
    (directory / "release/manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(release, "command", lambda *_: {"returncode": 0, "stdout": "abc\n"})
    monkeypatch.setattr(release, "baseline_check", lambda *_: {"passed": True})
    return artifact


def test_pristine_release_verifies(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch)
    assert release.verify(tmp_path)["passed"]


@pytest.mark.parametrize("change", ["edit", "remove", "extra"])
def test_artifact_changes_detected(tmp_path, monkeypatch, change):
    artifact = _manifest(tmp_path, monkeypatch)
    if change == "edit":
        artifact.write_text("altered")
    elif change == "remove":
        artifact.unlink()
    else:
        (artifact.parent / "unexpected.txt").write_text("not in the evidence manifest")
    assert not release.verify(tmp_path)["passed"]


def test_commit_change_detected(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "command", lambda *_: {"returncode": 0, "stdout": "different\n"})
    assert not release.verify(tmp_path)["passed"]


def test_source_selection_is_task_scoped(tmp_path):
    (tmp_path / "docs").mkdir()
    included = tmp_path / "docs/conference_release_guide.md"
    included.write_text("public guide")
    (tmp_path / "docs/other.md").write_text("not in this release source list")
    assert release.new_source_paths(tmp_path) == [included]


def test_symlinks_refused(tmp_path):
    artifact = tmp_path / "original.txt"
    artifact.write_text("original")
    link = tmp_path / "link.txt"
    link.symlink_to(artifact)
    with pytest.raises(ValueError, match="Symlink"):
        release.checked_files(tmp_path)


def test_changed_historical_results_fail_release_verification(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "baseline_check", lambda *_: {"passed": False})
    assert not release.verify(tmp_path)["passed"]


def test_subordinate_hash_chain_detects_changed_file(tmp_path):
    artifact = tmp_path / "sample.json"
    artifact.write_text("before")
    receipt = {"sample.json": release.digest(artifact)}
    assert release.verify_hash_map(tmp_path, receipt) == 1
    artifact.write_text("after")
    with pytest.raises(ValueError, match="mismatch"):
        release.verify_hash_map(tmp_path, receipt)


def test_subordinate_paths_cannot_escape_root(tmp_path):
    folder = tmp_path / "inside"
    folder.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("outside")
    with pytest.raises(ValueError, match="mismatch"):
        release.verify_hash_map(folder, {"../outside.json": release.digest(outside)})
