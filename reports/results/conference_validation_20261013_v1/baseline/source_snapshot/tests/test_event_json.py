"""Contract tests for the leakage-controlled Auger event JSON adapters."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

import auger_reco.data.event_json as event_json
from auger_reco.physics.plane_front import (
    angular_separation_deg,
    fit_plane_front,
)

MISSING = object()


class AccessGuardMapping(Mapping[str, object]):
    """Mapping that fails if production code reads a quarantined field."""

    def __init__(self, values: Mapping[str, object], allowed_keys: set[str]) -> None:
        self._values = values
        self._allowed_keys = allowed_keys

    def __getitem__(self, key: str) -> object:
        if key not in self._allowed_keys:
            raise AssertionError(f"Adapter accessed quarantined field {key!r}.")
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _station(
    station_id: int,
    *,
    x: float,
    y: float,
    z: float,
    time_ns: float,
    uncertainty_ns: float,
    selected: int,
) -> dict[str, object]:
    return {
        "id": station_id,
        "name": f"Station {station_id}",
        "x": x,
        "y": y,
        "z": z,
        "t": time_ns,
        "dt": uncertainty_ns,
        "signal": 10.0,
        "dsignal": 1.0,
        "sat": 0,
        "isSelected": selected,
        "spDistance": 999_999.0,
        "dspDistance": 999_999.0,
        "pmt1": [],
        "pmt2": [],
        "pmt3": [],
    }


@pytest.fixture
def event_document() -> dict[str, object]:
    return {
        "meta": {"release": 1, "format": 2},
        "info": {
            "id": 81_847_956_000,
            "date": "2008-07-03T10:05:59Z",
        },
        "flags": {"sd1500": 1, "sd750": 0},
        "sdrec": {
            "theta": 54.12,
            "dtheta": 0.4,
            "phi": 53.76,
            "dphi": 0.6,
            "energy": 56.83,
            "x": -5000.0,
            "y": 1000.0,
            "R": 12_000.0,
            "chi2": 3.2,
            "nbstat": 999,
            "recstations": [999, 998],
        },
        "stations": [
            _station(
                101,
                x=0.0,
                y=0.0,
                z=0.0,
                time_ns=10_000.0,
                uncertainty_ns=8.0,
                selected=1,
            ),
            _station(
                102,
                x=50_000.0,
                y=-70_000.0,
                z=800.0,
                time_ns=900_000.0,
                uncertainty_ns=50.0,
                selected=0,
            ),
            _station(
                103,
                x=1000.0,
                y=0.0,
                z=10.0,
                time_ns=11_000.0,
                uncertainty_ns=10.0,
                selected=1,
            ),
            _station(
                104,
                x=0.0,
                y=1000.0,
                z=20.0,
                time_ns=12_000.0,
                uncertainty_ns=12.0,
                selected=1,
            ),
            _station(
                105,
                x=-80_000.0,
                y=90_000.0,
                z=-500.0,
                time_ns=-400_000.0,
                uncertainty_ns=75.0,
                selected=0,
            ),
            _station(
                106,
                x=1000.0,
                y=1000.0,
                z=5.0,
                time_ns=13_000.0,
                uncertainty_ns=9.0,
                selected=1,
            ),
        ],
    }


def _issue_pairs(error: event_json.AugerEventSchemaError) -> set[tuple[str, str]]:
    return {(issue.code, issue.location) for issue in error.issues}


def test_extracts_only_officially_selected_stations_in_source_order(
    event_document: dict[str, object],
) -> None:
    result = event_json.adapt_auger_plane_front_input(event_document)

    assert result.event_id == 81_847_956_000
    assert result.canonical_event_id == "081847956000"
    assert result.embedded_release == "1"
    assert result.format_version == 2
    assert result.event_date == "2008-07-03T10:05:59Z"
    assert result.detector_array is event_json.DetectorArray.SD_1500
    assert result.selection_policy is event_json.StationSelection.OFFICIAL_SELECTED
    assert result.triggered_station_count == 6
    assert result.official_selected_station_count == 4
    assert result.number_of_stations == 4
    np.testing.assert_array_equal(result.station_ids, [101, 103, 104, 106])
    assert result.station_names == (
        "Station 101",
        "Station 103",
        "Station 104",
        "Station 106",
    )
    np.testing.assert_allclose(
        result.station_positions_m,
        [
            [0.0, 0.0, 0.0],
            [1000.0, 0.0, 10.0],
            [0.0, 1000.0, 20.0],
            [1000.0, 1000.0, 5.0],
        ],
    )
    np.testing.assert_allclose(result.observed_times_ns, [10_000, 11_000, 12_000, 13_000])
    np.testing.assert_allclose(result.timing_uncertainties_ns, [8.0, 10.0, 12.0, 9.0])

    arrays = (
        result.station_ids,
        result.station_positions_m,
        result.observed_times_ns,
        result.timing_uncertainties_ns,
    )
    assert result.station_ids.dtype == np.int64
    assert all(array.flags.c_contiguous for array in arrays)
    assert all(not array.flags.writeable for array in arrays)
    assert all(array.dtype == np.float64 for array in arrays[1:])


def test_all_triggered_stations_require_explicit_opt_in(
    event_document: dict[str, object],
) -> None:
    result = event_json.adapt_auger_plane_front_input(
        event_document,
        selection=event_json.StationSelection.ALL_TRIGGERED,
    )

    assert result.number_of_stations == 6
    np.testing.assert_array_equal(result.station_ids, [101, 102, 103, 104, 105, 106])
    assert result.selection_policy is event_json.StationSelection.ALL_TRIGGERED


def test_path_loader_matches_mapping_adapter(
    tmp_path,
    event_document: dict[str, object],
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event_document), encoding="utf-8")

    loaded = event_json.load_auger_plane_front_input(event_path)
    adapted = event_json.adapt_auger_plane_front_input(event_document)

    assert loaded.source_path == event_path.resolve()
    assert adapted.source_path is None
    assert loaded.event_id == adapted.event_id
    assert loaded.station_names == adapted.station_names
    np.testing.assert_array_equal(loaded.station_ids, adapted.station_ids)
    np.testing.assert_array_equal(loaded.station_positions_m, adapted.station_positions_m)
    np.testing.assert_array_equal(loaded.observed_times_ns, adapted.observed_times_ns)
    np.testing.assert_array_equal(
        loaded.timing_uncertainties_ns,
        adapted.timing_uncertainties_ns,
    )


def test_output_is_detached_frozen_and_read_only(
    event_document: dict[str, object],
) -> None:
    result = event_json.adapt_auger_plane_front_input(event_document)

    first_station = event_document["stations"][0]
    first_station["x"] = 987_654.0
    assert result.station_positions_m[0, 0] == 0.0

    with pytest.raises(FrozenInstanceError):
        result.event_id = 1  # type: ignore[misc]
    with pytest.raises(ValueError):
        result.station_positions_m[0, 0] = 1.0
    with pytest.raises(ValueError):
        result.observed_times_ns[0] = 1.0
    with pytest.raises(ValueError):
        result.timing_uncertainties_ns[0] = 1.0


def test_measurement_adapter_never_accesses_official_reconstruction(
    event_document: dict[str, object],
) -> None:
    safe_root_fields = {"meta", "info", "flags", "stations"}
    safe_station_fields = {"id", "name", "isSelected", "x", "y", "z", "t", "dt"}
    guarded_stations = [
        AccessGuardMapping(station, safe_station_fields)
        for station in event_document["stations"]
    ]
    guarded_root_values = {**event_document, "stations": guarded_stations}
    guarded_root = AccessGuardMapping(guarded_root_values, safe_root_fields)

    result = event_json.adapt_auger_plane_front_input(guarded_root)

    assert result.number_of_stations == 4
    forbidden_attributes = {
        "sdrec",
        "zenith_deg",
        "azimuth_deg",
        "energy_eev",
        "core_x_m",
        "core_y_m",
        "sp_distance_m",
    }
    assert forbidden_attributes.isdisjoint(result.__dataclass_fields__)


@pytest.mark.parametrize("reference_value", [None, "nonsense", [1, 2, 3]])
def test_reference_section_is_irrelevant_to_measurement_extraction(
    event_document: dict[str, object],
    reference_value: object,
) -> None:
    event_document["sdrec"] = reference_value

    result = event_json.adapt_auger_plane_front_input(event_document)

    assert result.number_of_stations == 4


def test_rejected_station_measurements_are_not_validated_by_default(
    event_document: dict[str, object],
) -> None:
    rejected_station = event_document["stations"][1]
    del rejected_station["x"]
    del rejected_station["dt"]

    selected = event_json.adapt_auger_plane_front_input(event_document)
    assert selected.number_of_stations == 4

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(
            event_document,
            selection=event_json.StationSelection.ALL_TRIGGERED,
        )

    assert ("missing_field", "/stations/1/x") in _issue_pairs(error_info.value)
    assert ("missing_field", "/stations/1/dt") in _issue_pairs(error_info.value)


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_code"),
    [
        ("x", MISSING, "missing_field"),
        ("y", "0.0", "wrong_type"),
        ("z", True, "wrong_type"),
        ("t", np.inf, "nonfinite_number"),
        ("dt", np.nan, "nonfinite_number"),
        ("dt", 0.0, "out_of_range"),
        ("dt", -1.0, "out_of_range"),
    ],
)
def test_invalid_selected_measurement_reports_field_location(
    event_document: dict[str, object],
    field: str,
    invalid_value: object,
    expected_code: str,
) -> None:
    station = event_document["stations"][0]
    if invalid_value is MISSING:
        del station[field]
    else:
        station[field] = invalid_value

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert (expected_code, f"/stations/0/{field}") in _issue_pairs(error_info.value)


def test_extreme_measurement_integer_becomes_structured_schema_error(
    event_document: dict[str, object],
) -> None:
    event_document["stations"][0]["x"] = 10**10_000

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert ("out_of_range", "/stations/0/x") in _issue_pairs(error_info.value)


@pytest.mark.parametrize(
    ("target", "value", "location"),
    [
        ("station", 2**63, "/stations/0/id"),
        ("event", 10**12, "/info/id"),
    ],
)
def test_out_of_range_identifiers_become_structured_schema_errors(
    event_document: dict[str, object],
    target: str,
    value: int,
    location: str,
) -> None:
    if target == "station":
        event_document["stations"][0]["id"] = value
    else:
        event_document["info"]["id"] = value

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert ("out_of_range", location) in _issue_pairs(error_info.value)


@pytest.mark.parametrize("invalid_flag", [-1, 2, "1", 1.0, True, False])
def test_invalid_station_selection_flag_is_rejected(
    event_document: dict[str, object],
    invalid_flag: object,
) -> None:
    event_document["stations"][0]["isSelected"] = invalid_flag

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert (
        "invalid_binary_flag",
        "/stations/0/isSelected",
    ) in _issue_pairs(error_info.value)


def test_duplicate_station_id_is_rejected(event_document: dict[str, object]) -> None:
    event_document["stations"][1]["id"] = 101

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert ("duplicate_station_id", "/stations/1/id") in _issue_pairs(error_info.value)


def test_schema_validation_reports_multiple_consumed_field_issues(
    event_document: dict[str, object],
) -> None:
    del event_document["stations"][0]["x"]
    event_document["stations"][0]["dt"] = 0.0

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    pairs = _issue_pairs(error_info.value)
    assert ("missing_field", "/stations/0/x") in pairs
    assert ("out_of_range", "/stations/0/dt") in pairs


def test_missing_station_name_uses_documented_fallback(
    event_document: dict[str, object],
) -> None:
    del event_document["stations"][0]["name"]

    result = event_json.adapt_auger_plane_front_input(event_document)

    assert result.station_names[0] == "101"
    assert result.quality_flags == ("station_name_fallbacks:1",)


def test_blank_station_name_is_rejected(event_document: dict[str, object]) -> None:
    event_document["stations"][0]["name"] = "   "

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert ("wrong_type", "/stations/0/name") in _issue_pairs(error_info.value)


def test_too_few_selected_stations_raise_structured_error(
    event_document: dict[str, object],
) -> None:
    event_document["stations"][5]["isSelected"] = 0

    with pytest.raises(event_json.AugerStationSelectionError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    error = error_info.value
    assert error.selection_policy is event_json.StationSelection.OFFICIAL_SELECTED
    assert error.available_stations == 3
    assert error.required_stations == 4


@pytest.mark.parametrize("invalid_minimum", [3, 0, -1])
def test_minimum_station_configuration_cannot_undercut_fitter_contract(
    event_document: dict[str, object],
    invalid_minimum: int,
) -> None:
    with pytest.raises(ValueError, match="minimum_stations must be at least 4"):
        event_json.adapt_auger_plane_front_input(
            event_document,
            minimum_stations=invalid_minimum,
        )


def test_boolean_minimum_station_configuration_is_rejected(
    event_document: dict[str, object],
) -> None:
    with pytest.raises(TypeError, match="minimum_stations must be an integer"):
        event_json.adapt_auger_plane_front_input(
            event_document,
            minimum_stations=True,
        )


def test_unknown_station_selection_policy_is_rejected(
    event_document: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="selection must be one of"):
        event_json.adapt_auger_plane_front_input(
            event_document,
            selection="sdrec.recstations",
        )


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (lambda event: [], "wrong_type", "/"),
        (lambda event: event.pop("meta"), "missing_field", "/meta"),
        (lambda event: event.pop("info"), "missing_field", "/info"),
        (lambda event: event.pop("flags"), "missing_field", "/flags"),
        (lambda event: event.pop("stations"), "missing_field", "/stations"),
        (lambda event: event.update(stations=[]), "empty_value", "/stations"),
        (lambda event: event.update(stations={}), "wrong_type", "/stations"),
    ],
)
def test_invalid_document_structure_is_rejected(
    event_document: dict[str, object],
    mutation,
    expected_code: str,
    expected_location: str,
) -> None:
    mutated = mutation(event_document)
    document = mutated if expected_location == "/" else event_document

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(document)

    assert (expected_code, expected_location) in _issue_pairs(error_info.value)


def test_unsupported_json_format_is_rejected(event_document: dict[str, object]) -> None:
    event_document["meta"]["format"] = 99

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_plane_front_input(event_document)

    assert (
        "unsupported_format_version",
        "/meta/format",
    ) in _issue_pairs(error_info.value)


@pytest.mark.parametrize(
    ("sd1500", "sd750", "expected_array", "expected_flags"),
    [
        (1, 0, event_json.DetectorArray.SD_1500, ()),
        (0, 1, event_json.DetectorArray.SD_750, ()),
        (
            1,
            1,
            event_json.DetectorArray.MIXED,
            ("mixed_surface_detector_flags",),
        ),
        (
            0,
            0,
            event_json.DetectorArray.UNCLASSIFIED,
            ("unclassified_surface_detector_array",),
        ),
    ],
)
def test_detector_flags_are_classified_and_reported(
    event_document: dict[str, object],
    sd1500: int,
    sd750: int,
    expected_array: event_json.DetectorArray,
    expected_flags: tuple[str, ...],
) -> None:
    event_document["flags"] = {"sd1500": sd1500, "sd750": sd750}

    result = event_json.adapt_auger_plane_front_input(event_document)

    assert result.detector_array is expected_array
    assert result.quality_flags == expected_flags


def test_malformed_json_raises_decode_error_with_original_cause(tmp_path) -> None:
    event_path = tmp_path / "broken.json"
    event_path.write_text('{"stations": [}', encoding="utf-8")

    with pytest.raises(event_json.AugerEventDecodeError) as error_info:
        event_json.load_auger_plane_front_input(event_path)

    error = error_info.value
    assert error.source_path == event_path.resolve()
    assert error.line == 1
    assert error.column is not None
    assert isinstance(error.__cause__, json.JSONDecodeError)


def test_missing_file_preserves_file_not_found_error(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        event_json.load_auger_plane_front_input(tmp_path / "absent.json")


def test_file_schema_error_records_resolved_source_path(
    tmp_path,
    event_document: dict[str, object],
) -> None:
    event_document["stations"][0]["dt"] = 0.0
    event_path = tmp_path / "invalid-event.json"
    event_path.write_text(json.dumps(event_document), encoding="utf-8")

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.load_auger_plane_front_input(event_path)

    assert error_info.value.source_path == event_path.resolve()


def test_direction_reference_is_separate_and_azimuth_is_normalized(
    event_document: dict[str, object],
) -> None:
    event_document["sdrec"]["phi"] = 360.0

    reference = event_json.adapt_auger_direction_reference(event_document)

    assert reference.event_id == 81_847_956_000
    assert reference.canonical_event_id == "081847956000"
    assert reference.embedded_release == "1"
    assert reference.format_version == 2
    assert reference.zenith_deg == pytest.approx(54.12)
    assert reference.azimuth_deg == pytest.approx(0.0)
    assert reference.zenith_uncertainty_deg == pytest.approx(0.4)
    assert reference.azimuth_uncertainty_deg == pytest.approx(0.6)


def test_direction_reference_path_loader_preserves_provenance(
    tmp_path,
    event_document: dict[str, object],
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event_document), encoding="utf-8")

    reference = event_json.load_auger_direction_reference(event_path)

    assert reference.source_path == event_path.resolve()
    assert reference.embedded_release == "1"
    assert reference.format_version == 2


@pytest.mark.parametrize("meta_value", [MISSING, {"release": 1, "format": 99}])
def test_direction_reference_requires_supported_format_metadata(
    event_document: dict[str, object],
    meta_value: object,
) -> None:
    if meta_value is MISSING:
        del event_document["meta"]
    else:
        event_document["meta"] = meta_value

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_direction_reference(event_document)

    assert any(issue.location.startswith("/meta") for issue in error_info.value.issues)


@pytest.mark.parametrize(
    ("theta", "phi"),
    [(0.0, 0.0), (90.0, 359.999)],
)
def test_direction_reference_accepts_physical_angle_boundaries(
    event_document: dict[str, object],
    theta: float,
    phi: float,
) -> None:
    event_document["sdrec"]["theta"] = theta
    event_document["sdrec"]["phi"] = phi
    event_document["sdrec"].pop("dtheta")
    event_document["sdrec"].pop("dphi")

    reference = event_json.adapt_auger_direction_reference(event_document)

    assert reference.zenith_deg == pytest.approx(theta)
    assert reference.azimuth_deg == pytest.approx(phi)
    assert reference.zenith_uncertainty_deg is None
    assert reference.azimuth_uncertainty_deg is None


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("theta", -0.1),
        ("theta", 90.1),
        ("theta", np.nan),
        ("phi", -0.1),
        ("phi", 360.1),
        ("phi", True),
    ],
)
def test_invalid_direction_reference_is_rejected(
    event_document: dict[str, object],
    field: str,
    invalid_value: object,
) -> None:
    event_document["sdrec"][field] = invalid_value

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_direction_reference(event_document)

    assert any(issue.location == f"/sdrec/{field}" for issue in error_info.value.issues)


def test_missing_reference_does_not_block_fit_input_but_blocks_reveal(
    event_document: dict[str, object],
) -> None:
    del event_document["sdrec"]

    fit_input = event_json.adapt_auger_plane_front_input(event_document)
    assert fit_input.number_of_stations == 4

    with pytest.raises(event_json.AugerEventSchemaError) as error_info:
        event_json.adapt_auger_direction_reference(event_document)

    assert ("missing_field", "/sdrec") in _issue_pairs(error_info.value)


def test_adapter_output_integrates_with_plane_front_fitter(
    event_document: dict[str, object],
) -> None:
    true_zenith_rad = np.deg2rad(42.0)
    true_azimuth_rad = np.deg2rad(55.0)
    true_sky_direction = np.array(
        [
            np.sin(true_zenith_rad) * np.cos(true_azimuth_rad),
            np.sin(true_zenith_rad) * np.sin(true_azimuth_rad),
            np.cos(true_zenith_rad),
        ]
    )
    true_propagation_direction = -true_sky_direction
    speed_m_per_ns = 0.299792458
    origin_time_ns = 100_000.0

    for station in event_document["stations"]:
        if station["isSelected"] == 1:
            position_m = np.array([station["x"], station["y"], station["z"]])
            station["t"] = float(
                origin_time_ns
                + position_m @ true_propagation_direction / speed_m_per_ns
            )

    fit_input = event_json.adapt_auger_plane_front_input(event_document)
    result = fit_plane_front(
        fit_input.station_positions_m,
        fit_input.observed_times_ns,
        fit_input.timing_uncertainties_ns,
    )

    assert angular_separation_deg(result.sky_direction, true_sky_direction) < 1.0e-6
