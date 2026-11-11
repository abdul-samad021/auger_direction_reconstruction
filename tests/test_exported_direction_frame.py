"""Tests for the optional, read-only geodetic audit (requires pyproj)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pyproj", reason="Optional coordinate audit dependency")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_exported_direction_frame.py"
SPEC = importlib.util.spec_from_file_location("export_frame_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_enu_axes_at_equator_prime_meridian() -> None:
    # East is +ECEF y, north is +ECEF z, up is +ECEF x.
    np.testing.assert_allclose(audit.basis(0, 0), [[0, 0, 1], [1, 0, 0], [0, 1, 0]])


@pytest.mark.parametrize("lon,lat", [(-69.25, -35.25), (23, 52), (180, 90), (-180, -90)])
def test_enu_basis_is_right_handed_and_orthonormal(lon, lat) -> None:
    matrix = audit.basis(lon, lat)
    np.testing.assert_allclose(matrix.T @ matrix, np.eye(3), atol=5e-16, rtol=0)
    assert np.linalg.det(matrix) == pytest.approx(1)
    np.testing.assert_allclose(np.cross(matrix[:, 0], matrix[:, 1]), matrix[:, 2], atol=1e-15)


@pytest.mark.parametrize("lon,lat", [(np.nan, 0), (0, np.inf), (0, 91), (0, -91)])
def test_nonfinite_or_invalid_latitude_rejected(lon, lat) -> None:
    with pytest.raises(ValueError):
        audit.basis(lon, lat)


@pytest.mark.parametrize(
    "phi,expected", [(0, [1, 0, 0]), (90, [0, 1, 0]), (180, [-1, 0, 0]), (270, [0, -1, 0])]
)
def test_azimuth_grows_east_to_north(phi, expected) -> None:
    np.testing.assert_allclose(audit.sky(90, phi), expected, atol=1e-15)


def test_full_3d_transform_round_trip_and_model_invariance() -> None:
    result = audit.mathematical_checks()
    assert result["status"] == "passed"
    assert result["maximum_timing_change_ns"] < 5e-11


def test_site_origin_resolved_from_utm_not_mistyped_latitude() -> None:
    lon, lat = audit.UTM.transform(audit.ORIGIN_E, audit.ORIGIN_N)
    assert lon == pytest.approx(-69.25, abs=1e-6)
    assert lat == pytest.approx(-35.25, abs=1e-6)
    assert abs(lat - (-35.35)) > 0.09


def test_identity_core_rotation_and_pairwise_angle_invariance() -> None:
    site = audit.basis(-69.25, -35.25)
    core = audit.basis(-69.5, -35.1)
    rotation = site.T @ core
    a, b = audit.sky(30, 23), audit.sky(35, 12)
    assert audit.angle(rotation @ a, rotation @ b) == pytest.approx(audit.angle(a, b), abs=1e-12)
    assert audit.angle(a, rotation @ b) == pytest.approx(audit.angle(rotation.T @ a, b), abs=1e-12)
    np.testing.assert_allclose(site.T @ site, np.eye(3), atol=1e-15)


def test_wgs84_ecef_conversion_independent_equatorial_anchor() -> None:
    np.testing.assert_allclose(audit.ECEF.transform(0, 0, 0), [6378137, 0, 0], atol=1e-8)


def test_existing_directory_rejected_before_reading_events(tmp_path) -> None:
    with pytest.raises(FileExistsError):
        audit.run(tmp_path / "absent_repository", tmp_path)


def test_invalid_envelope_rejected(tmp_path) -> None:
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps({"payload": {"training_ids": []}, "sha256": "0" * 64}))
    with pytest.raises(ValueError, match="Changed envelope"):
        audit.envelope(target)


def test_audit_output_never_overwrites(tmp_path) -> None:
    target = tmp_path / "receipt.json"
    audit.write_json(target, {"original": 1})
    with pytest.raises(FileExistsError):
        audit.write_json(target, {"changed": 2})
    assert json.loads(target.read_text()) == {"original": 1}


@pytest.mark.parametrize("values", [[], [np.nan], [np.inf]])
def test_nonfinite_summary_rejected(values) -> None:
    with pytest.raises(ValueError):
        audit.summary(values)
