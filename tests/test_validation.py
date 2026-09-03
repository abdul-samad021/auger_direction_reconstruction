from __future__ import annotations

import json

import pytest

from auger_reco.data.validate import validate_event


def _event() -> dict[str, object]:
    return {
        "meta": {"release": "3"},
        "info": {"id": 123},
        "flags": {"sd1500": 1, "sd750": 0},
        "sdrec": {"theta": 35.0, "phi": 120.0},
        "stations": [
            {
                "id": 1,
                "x": 0.0,
                "y": 0.0,
                "z": 1400.0,
                "t": 10.0,
                "dt": 5.0,
                "signal": 2.0,
                "isSelected": 1,
            },
            {
                "id": 2,
                "x": 1000.0,
                "y": 0.0,
                "z": 1401.0,
                "t": 12.0,
                "dt": 6.0,
                "signal": 3.0,
                "isSelected": 1,
            },
            {
                "id": 3,
                "x": 0.0,
                "y": 1000.0,
                "z": 1402.0,
                "t": 14.0,
                "dt": 7.0,
                "signal": 4.0,
                "isSelected": 1,
            },
            {
                "id": 4,
                "x": 1000.0,
                "y": 1000.0,
                "z": 1403.0,
                "t": 16.0,
                "dt": 8.0,
                "signal": 5.0,
                "isSelected": 1,
            },
        ],
    }


def test_valid_event(tmp_path):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(_event()), encoding="utf-8")

    report = validate_event(path)

    assert report["valid"] is True
    assert report["selected_stations"] == 4


def test_duplicate_station_is_rejected(tmp_path):
    event = _event()
    event["stations"][1]["id"] = 1
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate station id"):
        validate_event(path)


def test_missing_timing_uncertainty_is_rejected(tmp_path):
    event = _event()
    del event["stations"][0]["dt"]
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="missing: dt"):
        validate_event(path)


def test_fewer_than_four_selected_stations_is_rejected(tmp_path):
    event = _event()
    event["stations"][3]["isSelected"] = 0
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="only 3 selected stations; at least 4"):
        validate_event(path)


@pytest.mark.parametrize("dt", [0.0, -1.0])
def test_non_positive_timing_uncertainty_is_rejected(tmp_path, dt):
    event = _event()
    event["stations"][0]["dt"] = dt
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="non-positive dt"):
        validate_event(path)


@pytest.mark.parametrize("selection", [True, 1.0, "1", 2, -1])
def test_selection_flag_must_be_binary_json_integer(tmp_path, selection):
    event = _event()
    event["stations"][0]["isSelected"] = selection
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="isSelected outside integer 0 or 1"):
        validate_event(path)


def test_reference_reconstruction_is_optional(tmp_path):
    event = _event()
    del event["sdrec"]
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    report = validate_event(path)

    assert report["valid"] is True
    assert report["warnings"] == ["sdrec is absent; this event cannot provide SD direction targets"]


def test_signal_is_optional_for_timing_baseline(tmp_path):
    event = _event()
    for station in event["stations"]:
        del station["signal"]
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    report = validate_event(path)

    assert report["valid"] is True


def test_equal_station_times_can_represent_a_valid_vertical_front(tmp_path):
    event = _event()
    for station in event["stations"]:
        station["t"] = 10.0
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    report = validate_event(path)

    assert report["valid"] is True
