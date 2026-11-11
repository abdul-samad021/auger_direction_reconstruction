"""Notebook and command-line frame gates, using invented events only."""

from __future__ import annotations

import ast
import importlib.util
import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from auger_reco.data import direction_reference
from auger_reco.physics import plane_front

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_script("audit_training_pilot")
plotting = load_script("plot_training_pilot")


def notebook(name):
    return json.loads((ROOT / "notebooks" / f"{name}.ipynb").read_text())


def cell_source(book, index):
    return "".join(book["cells"][index]["source"])


@pytest.fixture
def reference_case(tmp_path):
    path = tmp_path / "invented.json"
    document = {
        "info": {"id": 12345},
        "meta": {"release": 1, "format": 2},
        "sdrec": {
            "theta": 42.0,
            "phi": 55.0,
            "dtheta": 0.4,
            "dphi": 0.6,
            "easting": 500000.0,
            "northing": 6080000.0,
        },
    }
    path.write_text(json.dumps(document))
    site = direction_reference.load_auger_site_direction_reference(path)
    payload = {
        "reference": asdict(site.reference),
        "reference_sky_direction_site": site.sky_direction_site.tolist(),
        "direction_frame_version": direction_reference.DIRECTION_FRAME_VERSION,
        "direction_frame_metadata": site.frame_metadata,
    }
    return path, site, payload


def test_audit_recomputes_common_frame_from_raw(reference_case):
    path, site, payload = reference_case
    vector, version = audit.reference_vector(payload, path)
    np.testing.assert_array_equal(vector, site.sky_direction_site)
    assert version == direction_reference.DIRECTION_FRAME_VERSION


@pytest.mark.parametrize("tamper", ["vector", "origin", "angles", "version"])
def test_audit_rejects_tampered_frame(reference_case, tamper):
    path, _, payload = reference_case
    if tamper == "vector":
        payload["reference_sky_direction_site"][0] += 0.01
    elif tamper == "origin":
        payload["direction_frame_metadata"]["site_origin"]["latitude_deg"] = 0
    elif tamper == "angles":
        payload["reference"]["azimuth_deg"] += 1
    else:
        payload["direction_frame_version"] = "unknown"
    with pytest.raises((ValueError, AssertionError)):
        audit.reference_vector(payload, path)


def test_legacy_audit_requires_optin_and_is_not_labeled_corrected(reference_case):
    path, _, payload = reference_case
    del payload["direction_frame_version"]
    with pytest.raises(ValueError, match="historical"):
        audit.reference_vector(payload, path)
    _, version = audit.reference_vector(payload, path, allow_legacy_reference_frame=True)
    assert version == audit.LEGACY_REFERENCE_FRAME
    assert version == plotting.LEGACY_REFERENCE_FRAME


@pytest.mark.parametrize("version", [None, "unknown"])
def test_audit_refuses_unapproved_frame_before_reading_event_data(tmp_path, version):
    payload = {"direction_frame_version": version}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    (tmp_path / "configuration.json").write_text(
        json.dumps({"payload": payload, "sha256": sha256(encoded.encode()).hexdigest()})
    )
    with pytest.raises(ValueError, match="frame"):
        audit.audit(tmp_path)


def test_plot_rejects_legacy_mixed_unknown_or_unstamped_frames():
    frame = pd.DataFrame({"separation_from_auger_deg": [0.1, 0.2]})
    with pytest.raises(ValueError, match="Unversioned"):
        plotting.validate_reference_frame(frame)
    assert (
        plotting.validate_reference_frame(frame, allow_legacy_reference_frame=True)
        == plotting.LEGACY_REFERENCE_FRAME
    )
    for values in (["unknown", "unknown"], [direction_reference.DIRECTION_FRAME_VERSION, None]):
        frame["direction_frame_version"] = values
        with pytest.raises(ValueError):
            plotting.validate_reference_frame(frame, allow_legacy_reference_frame=True)
    frame["direction_frame_version"] = direction_reference.DIRECTION_FRAME_VERSION
    assert plotting.validate_reference_frame(frame) == direction_reference.DIRECTION_FRAME_VERSION
    # Failed/unavailable comparisons need not pretend that a reference exists.
    frame.loc[1, ["direction_frame_version", "separation_from_auger_deg"]] = None
    assert plotting.validate_reference_frame(frame) == direction_reference.DIRECTION_FRAME_VERSION


@pytest.mark.parametrize(
    "name",
    [
        "03_reconstruct_first_real_event",
        "06_compare_real_event_front_models",
        "07_pre_pilot_diagnostics",
    ],
)
def test_notebook_syntax_and_coordinate_provenance(name):
    book = notebook(name)
    assert (
        book["metadata"]["direction_frame_version"] == direction_reference.DIRECTION_FRAME_VERSION
    )
    sources = []
    for cell in book["cells"]:
        source = "".join(cell["source"])
        if cell["cell_type"] == "code":
            ast.parse(source)
            sources.append(source)
    code = "\n".join(sources)
    assert "direction_reference" in code
    assert "event_json.load_auger_direction_reference" not in code
    # Outputs may legitimately be repopulated after a later verified Run All;
    # do not make a blank-output migration state a permanent testing contract.
    assert book["metadata"]["reference_outputs_cleared_on"] == "2026-10-14"


def test_first_event_notebook_comparison_uses_common_frame(reference_case, tmp_path):
    path, site, _ = reference_case
    output = tmp_path / "run"
    output.mkdir()
    fits = {
        name: SimpleNamespace(sky_direction=site.sky_direction_site)
        for name in ("timing", "uniform")
    }
    namespace = {
        "sha256": sha256,
        "EVENT_PATH": path,
        "event_sha256": sha256(path.read_bytes()).hexdigest(),
        "direction_reference": direction_reference,
        "plane_front": plane_front,
        "fit_input": site.reference,
        "np": np,
        "json": json,
        "RUN_DIR": output,
        "fits": fits,
        "display": lambda value: None,
        "prediction_summary": pd.DataFrame(
            {
                "weighting": ["timing", "uniform"],
                "zenith_deg": [42.0, 42.0],
                "azimuth_deg": [55.0, 55.0],
            }
        ),
    }
    book = notebook("03_reconstruct_first_real_event")
    exec(compile(cell_source(book, 22), "first-event-reference-cell", "exec"), namespace)
    result = namespace["comparison"]
    np.testing.assert_allclose(result["separation_from_auger_deg"], 0, atol=1e-12)
    assert (result["direction_frame_version"] == direction_reference.DIRECTION_FRAME_VERSION).all()
    assert not np.isclose(result["auger_site_zenith_deg"].iloc[0], site.reference.zenith_deg)
    metadata = json.loads((output / "direction_frame_metadata.json").read_text())
    assert metadata["method_version"] == direction_reference.DIRECTION_FRAME_VERSION


def test_real_front_notebook_compares_after_frozen_prediction(reference_case, tmp_path):
    path, site, _ = reference_case
    identity = site.reference.canonical_event_id
    output = tmp_path / "run"
    (output / identity).mkdir(parents=True)
    records = pd.DataFrame(
        [
            {
                "event_id": identity,
                "stage": "full",
                "model": "plane",
                "weighting": "timing",
                "success": True,
                "sky_x": site.sky_direction_site[0],
                "sky_y": site.sky_direction_site[1],
                "sky_z": site.sky_direction_site[2],
                "zenith_deg": 42.0,
                "azimuth_deg": 55.0,
                "delay_at_1km_ns": 0.0,
                "reduced_chi_square": 1.0,
                "rms_residual_ns": 10.0,
                "quality_flags": "",
            }
        ]
    )
    namespace = {
        "sha256": sha256,
        "direction_reference": direction_reference,
        "plane_front": plane_front,
        "np": np,
        "pd": pd,
        "require_state": lambda *names: None,
        "display": lambda value: None,
        "event_runs": {identity: (site.reference, None, None)},
        "records": records,
        "event_paths": {identity: path},
        "initial_event_hashes": {identity: sha256(path.read_bytes()).hexdigest()},
        "RUN_DIR": output,
        "FOCUS_ID": identity,
        "write_json": lambda path, data: path.write_text(json.dumps(data)),
    }
    book = notebook("06_compare_real_event_front_models")
    frozen = cell_source(book, 6)
    assert "all_fit_records_before_reference.csv" in frozen
    assert "load_auger_site_direction_reference" not in frozen
    exec(compile(cell_source(book, 8), "front-reference-cell", "exec"), namespace)
    result = namespace["comparison"]
    assert result["separation_from_auger_deg"].iloc[0] == pytest.approx(0, abs=1e-12)
    assert "direction_frame_version" in result
    assert "separation_from_auger_deg" not in records  # Original prediction table unchanged.
