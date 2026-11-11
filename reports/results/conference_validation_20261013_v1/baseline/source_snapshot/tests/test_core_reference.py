"""Strict core-only adapter contracts; fixtures contain no protected events."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import numpy as np
import pytest

from auger_reco.data import core_reference, event_json


@pytest.fixture
def document() -> dict:
    """Minimal invented event with metre-scale reference values."""

    return {
        "info": {"id": 12345},
        "meta": {"release": 1, "format": 2},
        "sdrec": {"x": -1200.5, "y": 250, "z": 12.5, "dx": 10.0, "dy": 20.0},
    }


def test_valid_core_preserves_units_identity_and_provenance(document, tmp_path):
    path = tmp_path / "not-opened.json"
    result = core_reference.adapt_auger_core_reference(document, source_path=path)
    np.testing.assert_array_equal(result.position_m, [-1200.5, 250.0, 12.5])
    assert result.position_m.shape == (3,)
    assert result.position_m.dtype == np.float64
    assert result.event_id == 12345
    assert result.canonical_event_id == "000000012345"
    assert result.embedded_release == "1"
    assert result.format_version == 2
    assert result.source_path == path.resolve()
    assert result.source == "sdrec"
    assert result.position_field_paths == ("/sdrec/x", "/sdrec/y", "/sdrec/z")
    assert result.uncertainty_field_paths == ("/sdrec/dx", "/sdrec/dy")
    assert result.uncertainty_x_m == 10.0
    assert result.uncertainty_y_m == 20.0
    assert not path.exists()  # Provenance-only in-memory adapter performs no I/O.


def test_frozen_output_is_an_independent_readonly_copy(document):
    result = core_reference.adapt_auger_core_reference(document)
    document["sdrec"]["x"] = 999.0
    assert result.position_m[0] == -1200.5
    with pytest.raises(ValueError):
        result.position_m[0] = 999.0
    with pytest.raises(ValueError):
        result.position_m.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        result.event_id = 999


@pytest.mark.parametrize("missing", [("dx",), ("dy",), ("dx", "dy")])
def test_missing_uncertainties_are_unknown_not_zero(document, missing):
    for name in missing:
        del document["sdrec"][name]
    result = core_reference.adapt_auger_core_reference(document)
    assert result.uncertainty_x_m == (None if "dx" in missing else 10.0)
    assert result.uncertainty_y_m == (None if "dy" in missing else 20.0)


@pytest.mark.parametrize("name", ["x", "y", "z"])
@pytest.mark.parametrize("bad", [None, True, "1.2", [], float("nan"), float("inf"), 10**400])
def test_required_coordinates_reject_invalid_values(document, name, bad):
    document["sdrec"][name] = bad
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert [issue.location for issue in caught.value.issues] == [f"/sdrec/{name}"]


@pytest.mark.parametrize("name", ["x", "y", "z"])
def test_coordinate_is_required(document, name):
    del document["sdrec"][name]
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert [(issue.code, issue.location) for issue in caught.value.issues] == [
        ("missing_field", f"/sdrec/{name}")
    ]


@pytest.mark.parametrize("name", ["dx", "dy"])
@pytest.mark.parametrize("bad", [None, False, "10", 0.0, -1.0, float("nan"), float("inf")])
def test_present_uncertainties_must_be_positive_finite_numbers(document, name, bad):
    document["sdrec"][name] = bad
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert [issue.location for issue in caught.value.issues] == [f"/sdrec/{name}"]


@pytest.mark.parametrize("bad", [None, [], True, "event"])
def test_root_requires_mapping(bad):
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(bad)
    assert caught.value.issues[0].location == "/"


@pytest.mark.parametrize("name", ["meta", "info", "sdrec"])
def test_missing_parent_has_only_one_structured_issue(document, name):
    del document[name]
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert [(issue.code, issue.location) for issue in caught.value.issues] == [
        ("missing_field", f"/{name}")
    ]


@pytest.mark.parametrize("name", ["meta", "info", "sdrec"])
def test_invalid_parent_does_not_fabricate_missing_children(document, name):
    document[name] = None
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert [(issue.code, issue.location) for issue in caught.value.issues] == [
        ("wrong_type", f"/{name}")
    ]


@pytest.mark.parametrize(
    ("parent", "name", "bad"),
    [
        ("info", "id", True),
        ("info", "id", -1),
        ("info", "id", 10**12),
        ("meta", "release", "1"),
        ("meta", "release", -1),
        ("meta", "format", 99),
    ],
)
def test_metadata_matches_existing_reference_rules(document, parent, name, bad):
    document[parent][name] = bad
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document)
    assert caught.value.issues[0].location == f"/{parent}/{name}"


class OnlyAllowedFields(Mapping[str, object]):
    """Fail even on attempted access to a quarantined reconstruction field."""

    def __init__(self, values: Mapping[str, object]):
        self.values = values

    def __getitem__(self, key: str) -> object:
        if key not in self.values:
            raise AssertionError(f"Unexpected field accessed: {key}")
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def test_no_direction_or_other_reconstructed_quantities_are_consumed(document):
    guarded = OnlyAllowedFields(
        {name: OnlyAllowedFields(value) for name, value in document.items()}
    )
    result = core_reference.adapt_auger_core_reference(guarded)
    assert result.event_id == 12345
    names = {entry.name for entry in fields(result)}
    assert names.isdisjoint({"zenith_deg", "azimuth_deg", "radius_m", "energy", "covariance"})


def test_metadata_matches_direction_reference_without_requiring_angles(document):
    result = core_reference.adapt_auger_core_reference(document)
    document["sdrec"].update(theta=42.0, phi=55.0)
    direction = event_json.adapt_auger_direction_reference(document)
    for name in ("event_id", "canonical_event_id", "embedded_release", "format_version"):
        assert getattr(result, name) == getattr(direction, name)


def test_multiple_issues_are_retained_with_source(document, tmp_path):
    document["sdrec"].update(x=None, y=True, dy=-1)
    path = tmp_path / "bad.json"
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        core_reference.adapt_auger_core_reference(document, source_path=path)
    assert {issue.location for issue in caught.value.issues} == {
        "/sdrec/x",
        "/sdrec/y",
        "/sdrec/dy",
    }
    assert caught.value.source_path == path.resolve()


def test_file_loader_accepts_utf8_bom_and_resolves_path(document, tmp_path, monkeypatch):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(document), encoding="utf-8-sig")
    monkeypatch.chdir(tmp_path)
    result = core_reference.load_auger_core_reference(Path("event.json"))
    assert result.source_path == path.resolve()
    np.testing.assert_array_equal(result.position_m, [-1200.5, 250.0, 12.5])


@pytest.mark.parametrize("text", ['{"sdrec": {}, "sdrec": {}}', '{"bad":', "not json"])
def test_malformed_or_duplicate_key_json_is_rejected(tmp_path, text):
    path = tmp_path / "event.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(event_json.AugerEventDecodeError):
        core_reference.load_auger_core_reference(path)


def test_non_utf8_is_rejected(tmp_path):
    path = tmp_path / "event.json"
    path.write_bytes(b"\xff\xfe invalid UTF-8")
    with pytest.raises(event_json.AugerEventDecodeError):
        core_reference.load_auger_core_reference(path)


def test_missing_file_remains_filesystem_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        core_reference.load_auger_core_reference(tmp_path / "absent.json")
