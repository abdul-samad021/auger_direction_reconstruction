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
            {"id": 1, "x": 0.0, "y": 0.0, "z": 1400.0, "t": 10.0, "signal": 2.0, "isSelected": 1},
            {
                "id": 2,
                "x": 1000.0,
                "y": 0.0,
                "z": 1401.0,
                "t": 12.0,
                "signal": 3.0,
                "isSelected": 1,
            },
            {
                "id": 3,
                "x": 0.0,
                "y": 1000.0,
                "z": 1402.0,
                "t": 14.0,
                "signal": 4.0,
                "isSelected": 1,
            },
        ],
    }


def test_valid_event(tmp_path):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(_event()), encoding="utf-8")

    report = validate_event(path)

    assert report["valid"] is True
    assert report["selected_stations"] == 3


def test_duplicate_station_is_rejected(tmp_path):
    event = _event()
    event["stations"][1]["id"] = 1
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate station id"):
        validate_event(path)
