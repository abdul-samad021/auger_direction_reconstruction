from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED_TOP_LEVEL = {"meta", "info", "flags", "stations"}
REQUIRED_STATION_FIELDS = {"id", "x", "y", "z", "t", "dt", "isSelected"}
MINIMUM_SELECTED_STATIONS = 4


def _finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _binary_integer(value: Any) -> bool:
    """Return whether a JSON value is exactly the integer zero or one."""
    return type(value) is int and value in {0, 1}


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Event JSON must contain one object at the top level.")
    return value


def validate_event(path: Path) -> dict[str, object]:
    event = _load_json_object(path)
    errors: list[str] = []
    warnings: list[str] = []

    missing_sections = sorted(REQUIRED_TOP_LEVEL - event.keys())
    if missing_sections:
        errors.append(f"Missing top-level sections: {', '.join(missing_sections)}")

    stations = event.get("stations")
    if not isinstance(stations, list) or not stations:
        errors.append("stations must be a non-empty list")
        stations = []

    selected: list[dict[str, Any]] = []
    seen_ids: set[int | str] = set()
    for index, station in enumerate(stations):
        if not isinstance(station, dict):
            errors.append(f"station {index} is not an object")
            continue
        missing_fields = REQUIRED_STATION_FIELDS - station.keys()
        if missing_fields:
            errors.append(f"station {index} missing: {', '.join(sorted(missing_fields))}")
            continue
        station_id = station["id"]
        if not isinstance(station_id, int | str) or isinstance(station_id, bool):
            errors.append(f"station {index} has an invalid id")
        elif station_id in seen_ids:
            errors.append(f"duplicate station id: {station_id}")
        else:
            seen_ids.add(station_id)

        selection = station["isSelected"]
        if not _binary_integer(selection):
            errors.append(f"station {station_id} has isSelected outside integer 0 or 1")
        elif selection == 1:
            selected.append(station)

    if len(selected) < MINIMUM_SELECTED_STATIONS:
        errors.append(
            f"only {len(selected)} selected stations; "
            f"at least {MINIMUM_SELECTED_STATIONS} are required"
        )

    for station in selected:
        station_id = station["id"]
        for field in ("x", "y", "z", "t", "dt"):
            if not _finite_number(station[field]):
                errors.append(f"station {station_id} has non-finite or non-numeric {field}")

        if _finite_number(station["dt"]) and station["dt"] <= 0:
            errors.append(f"station {station_id} has a non-positive dt")

        signal = station.get("signal")
        if signal is not None and not _finite_number(signal):
            errors.append(f"station {station_id} has a non-finite or non-numeric signal")
        elif _finite_number(signal) and signal < 0:
            errors.append(f"station {station_id} has a negative signal")

    if selected:
        xy = [
            (station["x"], station["y"])
            for station in selected
            if _finite_number(station["x"]) and _finite_number(station["y"])
        ]
        if len(xy) > 1 and len(set(xy)) == 1:
            warnings.append(
                "selected stations have no horizontal spatial spread; "
                "the reconstruction geometry may be degenerate"
            )

    sdrec = event.get("sdrec")
    if not isinstance(sdrec, dict):
        warnings.append("sdrec is absent; this event cannot provide SD direction targets")
    else:
        theta = sdrec.get("theta")
        phi = sdrec.get("phi")
        if not _finite_number(theta) or not 0 <= theta <= 90:
            errors.append("sdrec.theta is missing or outside 0–90 degrees")
        if not _finite_number(phi) or not 0 <= phi <= 360:
            errors.append("sdrec.phi is missing or outside 0–360 degrees")

    report: dict[str, object] = {
        "kind": "event-json",
        "path": str(path),
        "valid": not errors,
        "event_id": event.get("info", {}).get("id")
        if isinstance(event.get("info"), dict)
        else None,
        "stations": len(stations),
        "selected_stations": len(selected),
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise ValueError(json.dumps(report, indent=2))
    return report


def validate_zip(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
        ]
        corrupt_member = archive.testzip()

    errors: list[str] = []
    if not names:
        errors.append("archive is empty")
    if unsafe:
        errors.append(f"archive contains unsafe paths: {unsafe[:3]}")
    if corrupt_member:
        errors.append(f"archive member failed CRC validation: {corrupt_member}")

    report: dict[str, object] = {
        "kind": "zip-archive",
        "path": str(path),
        "valid": not errors,
        "members": len(names),
        "errors": errors,
        "first_members": names[:10],
    }
    if errors:
        raise ValueError(json.dumps(report, indent=2))
    return report


def validate_path(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        return validate_event(path)
    if path.suffix.lower() == ".zip":
        return validate_zip(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def inspect_event(path: Path) -> dict[str, object]:
    event = _load_json_object(path)
    stations = event.get("stations", [])
    selected = [
        station
        for station in stations
        if isinstance(station, dict) and station.get("isSelected") == 1
    ]
    flags = event.get("flags", {})
    sdrec = event.get("sdrec", {})

    if flags.get("sd1500") == 1:
        detector = "SD-1500"
    elif flags.get("sd750") == 1:
        detector = "SD-750"
    else:
        detector = "unclassified"

    return {
        "event_id": event.get("info", {}).get("id"),
        "date": event.get("info", {}).get("date"),
        "release": event.get("meta", {}).get("release"),
        "detector": detector,
        "stations_total": len(stations),
        "stations_selected": len(selected),
        "reference_only": {
            "theta_deg": sdrec.get("theta"),
            "phi_deg": sdrec.get("phi"),
            "energy_eev": sdrec.get("energy"),
        },
        "warning": "reference_only values are evaluation metadata, never baseline inputs",
    }
