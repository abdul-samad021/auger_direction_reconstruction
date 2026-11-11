"""Follow-up evidence checks preserve the preceding immutable release."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/freeze_reliability_followup.py"
SPEC = importlib.util.spec_from_file_location("freeze_reliability_followup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_plot_amendment_does_not_allow_scientific_function_changes():
    before = "def science(x): return x * 2\ndef _figures(x): return x\n"
    after = "def science(x): return x * 2\ndef _figures(x): return max(x, 0)\n"
    assert release.only_plot_changed(before, after)
    assert not release.only_plot_changed(before, after.replace("x * 2", "x * 3"))
    assert not release.only_plot_changed(before, "NEW_THRESHOLD = 10\n" + after)


def test_release_refuses_overwrite_and_missing_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        release.freeze(tmp_path)
    (tmp_path / release.BASE / "release").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        release.freeze(tmp_path)


def sample_release(tmp_path, monkeypatch):
    base = tmp_path / release.BASE
    (base / "release").mkdir(parents=True)
    artifact = base / "result.json"
    artifact.write_text("original")
    manifest = {"artifact_sha256": {str(artifact.relative_to(tmp_path)): release.digest(artifact)}}
    (base / "release/manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(release, "original_seal", lambda root: {"passed": True})
    return artifact


def test_release_verifies_pristine_artifacts(tmp_path, monkeypatch):
    sample_release(tmp_path, monkeypatch)
    assert release.verify(tmp_path)["passed"]


@pytest.mark.parametrize("change", ["overwrite", "delete", "extra"])
def test_release_detects_evidence_changes(tmp_path, monkeypatch, change):
    path = sample_release(tmp_path, monkeypatch)
    if change == "overwrite":
        path.write_text("changed")
    elif change == "delete":
        path.unlink()
    else:
        (path.parent / "unrecorded.json").write_text("extra")
    assert not release.verify(tmp_path)["passed"]


def test_original_seal_must_be_successful(tmp_path, monkeypatch):
    monkeypatch.setattr(
        release, "run_command", lambda *args: {"returncode": 0, "stdout": '{"passed": false}'}
    )
    with pytest.raises(RuntimeError, match="evidence changed"):
        release.original_seal(tmp_path)
