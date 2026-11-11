"""Common-frame reference contracts using invented events, never held-out data."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from pyproj import Transformer
from pyproj.exceptions import ProjError

from auger_reco.data import direction_reference as frame
from auger_reco.data import event_json


@pytest.fixture
def document() -> dict:
    """Use the exact supplied site origin as a synthetic core by default."""

    return {
        "info": {"id": 12345},
        "meta": {"release": 1, "format": 2},
        "sdrec": {
            "theta": 42.0,
            "phi": 55.0,
            "dtheta": 0.4,
            "dphi": 0.6,
            "easting": frame.SITE_ORIGIN_EASTING_M,
            "northing": frame.SITE_ORIGIN_NORTHING_M,
        },
    }


def _sky(theta_deg: float, phi_deg: float) -> np.ndarray:
    theta, phi = np.deg2rad([theta_deg, phi_deg])
    return np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])


def _ecef_components(sky: np.ndarray, longitude: float, latitude: float) -> np.ndarray:
    """Independent scalar expansion, without using the production basis helper."""

    lon, lat = np.deg2rad([longitude, latitude])
    east, north, up = sky
    return np.array(
        [
            -np.sin(lon) * east
            - np.sin(lat) * np.cos(lon) * north
            + np.cos(lat) * np.cos(lon) * up,
            np.cos(lon) * east - np.sin(lat) * np.sin(lon) * north + np.cos(lat) * np.sin(lon) * up,
            np.cos(lat) * north + np.sin(lat) * up,
        ]
    )


def test_identity_rotation_and_native_metadata_are_preserved(document, tmp_path):
    original = deepcopy(document)
    path = tmp_path / "provenance-only.json"
    result = frame.adapt_auger_site_direction_reference(document, source_path=path)

    assert result.reference == event_json.adapt_auger_direction_reference(
        document, source_path=path
    )
    assert result.reference.canonical_event_id == "000000012345"
    assert result.reference.zenith_uncertainty_deg == 0.4
    assert result.reference.azimuth_uncertainty_deg == 0.6
    np.testing.assert_allclose(result.sky_direction_site, _sky(42, 55), atol=3e-16, rtol=0)
    assert document == original
    assert not path.exists()  # The mapping adapter never opens its provenance path.


@pytest.mark.parametrize(
    "theta,phi,expected",
    [
        (0, 0, [0, 0, 1]),
        (90, 0, [1, 0, 0]),
        (90, 90, [0, 1, 0]),
        (90, 180, [-1, 0, 0]),
        (90, 270, [0, -1, 0]),
        (90, 360, [1, 0, 0]),
    ],
)
def test_cardinal_azimuths_follow_east_north_west_south(document, theta, phi, expected):
    document["sdrec"].update(theta=theta, phi=phi)
    result = frame.adapt_auger_site_direction_reference(document)
    np.testing.assert_allclose(result.sky_direction_site, expected, atol=1e-15, rtol=0)


@pytest.mark.parametrize("longitude,latitude", [(-69.50, -35.10), (-69.0, -35.5)])
@pytest.mark.parametrize("theta,phi", [(0, 0), (42, 55), (60, 240), (90, 90)])
def test_displaced_core_rotation_preserves_physical_ecef_direction(
    document, longitude, latitude, theta, phi
):
    to_utm = Transformer.from_crs("EPSG:4326", frame.CORE_COORDINATE_CRS, always_xy=True)
    easting, northing = to_utm.transform(longitude, latitude)
    document["sdrec"].update(easting=easting, northing=northing, theta=theta, phi=phi)
    result = frame.adapt_auger_site_direction_reference(document)

    origin = result.frame_metadata["site_origin"]
    actual_ecef = _ecef_components(
        result.sky_direction_site, origin["longitude_deg"], origin["latitude_deg"]
    )
    expected_ecef = _ecef_components(_sky(theta, phi), longitude, latitude)
    np.testing.assert_allclose(actual_ecef, expected_ecef, atol=1e-15, rtol=0)
    assert result.core_longitude_deg == pytest.approx(longitude, abs=1e-12)
    assert result.core_latitude_deg == pytest.approx(latitude, abs=1e-12)
    assert np.linalg.norm(result.sky_direction_site) == pytest.approx(1, abs=1e-15)
    # Applying no rotation or the inverse rotation must not pass this test.
    assert np.linalg.norm(result.sky_direction_site - _sky(theta, phi)) > 1e-4


def test_local_horizon_is_not_artificially_clipped_to_site_horizon(document):
    to_utm = Transformer.from_crs("EPSG:4326", frame.CORE_COORDINATE_CRS, always_xy=True)
    easting, northing = to_utm.transform(-69.25, -35.15)
    document["sdrec"].update(easting=easting, northing=northing, theta=90, phi=90)
    result = frame.adapt_auger_site_direction_reference(document)
    assert result.sky_direction_site[2] < 0


def test_output_is_detached_frozen_and_cannot_be_made_writeable(document):
    result = frame.adapt_auger_site_direction_reference(document)
    expected = result.sky_direction_site.copy()
    document["sdrec"].update(easting=400000, phi=180)
    np.testing.assert_array_equal(result.sky_direction_site, expected)
    assert result.sky_direction_site.dtype == np.float64
    assert result.sky_direction_site.shape == (3,)
    assert result.sky_direction_site.flags.c_contiguous
    with pytest.raises(ValueError):
        result.sky_direction_site[0] = 0
    with pytest.raises(ValueError):
        result.sky_direction_site.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        result.core_easting_m = 0


def test_provenance_is_finite_json_and_fresh_including_nested_values(document):
    result = frame.adapt_auger_site_direction_reference(document)
    metadata = result.frame_metadata
    json.dumps(metadata, allow_nan=False)
    assert metadata["method_version"] == "auger-core-enu-to-site-enu-wgs84-v1"
    assert metadata["core_coordinate_crs"] == "EPSG:32719"
    assert metadata["site_origin"]["longitude_deg"] == pytest.approx(-69.25, abs=1e-6)
    assert metadata["site_origin"]["latitude_deg"] == pytest.approx(-35.25, abs=1e-6)
    assert metadata["pyproj_version"]
    assert metadata["proj_version"]
    metadata["site_origin"]["latitude_deg"] = 99
    metadata["consumed_coordinate_fields"].append("forbidden")
    assert result.frame_metadata["site_origin"]["latitude_deg"] < 0
    assert result.frame_metadata["consumed_coordinate_fields"] == [
        "/sdrec/easting",
        "/sdrec/northing",
    ]


@pytest.mark.parametrize("name", ["easting", "northing"])
@pytest.mark.parametrize("bad", [None, True, False, "477256", [], np.nan, np.inf, -np.inf, 10**400])
def test_required_coordinates_reject_invalid_numbers_without_fallback(document, name, bad):
    document["sdrec"][name] = bad
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(document)
    assert [issue.location for issue in caught.value.issues] == [f"/sdrec/{name}"]


@pytest.mark.parametrize("name", ["easting", "northing"])
def test_coordinate_is_required(document, name):
    del document["sdrec"][name]
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(document)
    assert [(issue.code, issue.location) for issue in caught.value.issues] == [
        ("missing_field", f"/sdrec/{name}")
    ]


@pytest.mark.parametrize(
    "easting,northing",
    [
        (0, 6099203.68),
        (1000000, 6099203.68),
        (477256.66, -1),
        (477256.66, 10000001),
        (100000, 6099203.68),
        (477256.66, 0),
    ],
)
def test_coordinate_domain_rejects_out_of_zone_locations(document, easting, northing):
    document["sdrec"].update(easting=easting, northing=northing)
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(document)
    assert caught.value.issues[0].code == "out_of_range"


def test_multiple_coordinate_issues_keep_source_path(document, tmp_path):
    document["sdrec"].update(easting=True, northing=np.nan)
    path = tmp_path / "not-opened.json"
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(document, source_path=path)
    assert {issue.location for issue in caught.value.issues} == {
        "/sdrec/easting",
        "/sdrec/northing",
    }
    assert caught.value.source_path == path.resolve()


@pytest.mark.parametrize("bad", [None, [], True, "event"])
def test_native_schema_errors_are_not_hidden(bad):
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(bad)
    assert caught.value.issues[0].location == "/"


class _OnlyAllowedFields(Mapping[str, object]):
    """Any attempted access beyond the documented evaluation inputs fails."""

    def __init__(self, values):
        self.values = values

    def __getitem__(self, key: str) -> object:
        if key not in self.values:
            raise AssertionError(f"Unexpected field accessed: {key}")
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def test_no_station_measurements_altitude_or_other_reconstruction_fields_are_consumed(document):
    guarded = _OnlyAllowedFields(
        {name: _OnlyAllowedFields(value) for name, value in document.items()}
    )
    result = frame.adapt_auger_site_direction_reference(guarded)
    assert result.reference.event_id == 12345


@pytest.mark.parametrize("failure", [ProjError("invalid projection"), (np.nan, -35)])
def test_projection_errors_and_nonfinite_results_fail_closed(document, monkeypatch, failure):
    class BadTransformer:
        def transform(self, *args, **kwargs):
            if isinstance(failure, Exception):
                raise failure
            return failure

    monkeypatch.setattr(frame, "_utm_to_geodetic", lambda: BadTransformer())
    with pytest.raises(event_json.AugerEventSchemaError) as caught:
        frame.adapt_auger_site_direction_reference(document)
    assert caught.value.issues[0].location == "/sdrec"


def test_file_loader_matches_mapping_supports_bom_and_resolves_path(
    document, tmp_path, monkeypatch
):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(document), encoding="utf-8-sig")
    monkeypatch.chdir(tmp_path)
    loaded = frame.load_auger_site_direction_reference("event.json")
    mapped = frame.adapt_auger_site_direction_reference(document, source_path=path)
    assert loaded.reference == mapped.reference
    assert loaded.frame_metadata == mapped.frame_metadata
    np.testing.assert_array_equal(loaded.sky_direction_site, mapped.sky_direction_site)


@pytest.mark.parametrize("text", ['{"sdrec": {}, "sdrec": {}}', '{"bad":', "not json"])
def test_loader_reuses_duplicate_key_and_decode_error_contract(tmp_path, text):
    path = tmp_path / "event.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(event_json.AugerEventDecodeError):
        frame.load_auger_site_direction_reference(path)


def test_loader_keeps_missing_file_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        frame.load_auger_site_direction_reference(tmp_path / "missing.json")
