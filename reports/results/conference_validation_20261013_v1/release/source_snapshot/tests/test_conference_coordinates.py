"""Independent tests for the bounded conference coordinate audit."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_conference_coordinates.py"
SPEC = importlib.util.spec_from_file_location("conference_coordinate_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_origin_and_signed_map_basis() -> None:
    np.testing.assert_array_equal(audit.site_to_tutorial_utm([0, 0, 0]), audit.ORIGIN)
    points = np.array([[1000, 0, 0], [0, 1000, 0], [0, 0, 100]])
    offsets = audit.site_to_tutorial_utm(points) - audit.ORIGIN
    np.testing.assert_allclose(offsets[0], [999.397, 2.52, 1e6 / 12_736_000], atol=1e-9)
    np.testing.assert_allclose(offsets[1], [-2.52, 999.397, 1e6 / 12_736_000], atol=1e-9)
    np.testing.assert_allclose(offsets[2], [0, 0, 100], atol=1e-9)


def test_map_round_trip_and_no_input_mutation() -> None:
    points = np.random.default_rng(73).uniform(-40_000, 40_000, (50, 3))
    original = points.copy()
    restored = audit.tutorial_utm_to_site(audit.site_to_tutorial_utm(points))
    np.testing.assert_allclose(restored, points, atol=1e-8, rtol=0)
    np.testing.assert_array_equal(points, original)


@pytest.mark.parametrize("bad", [1, [1, 2], [[1, 2]], [1, 2, np.nan], [1, np.inf, 2]])
def test_invalid_positions_rejected(bad) -> None:
    with pytest.raises(ValueError, match="finite"):
        audit.site_to_tutorial_utm(bad)


def test_counterfactual_is_not_a_rigid_frame_change() -> None:
    points = np.array([[0, 0, 0], [10_000, 0, 0]], dtype=float)
    altered = audit.counterfactual_shift(points)
    assert altered[1, 2] == pytest.approx(1e8 / 12_736_000)
    assert np.linalg.norm(altered[1] - altered[0]) > np.linalg.norm(points[1] - points[0])
    np.testing.assert_array_equal(points[:, 2], 0)


def test_z_rotation_orthogonal_and_preserves_handedness() -> None:
    matrix = audit.rotation_z(137)
    np.testing.assert_allclose(matrix.T @ matrix, np.eye(3), rtol=0, atol=1e-15)
    assert np.linalg.det(matrix) == pytest.approx(1)
    np.testing.assert_allclose(matrix @ [0, 0, 1], [0, 0, 1], rtol=0, atol=1e-15)


def test_independent_forward_sign_and_curvature() -> None:
    positions = np.array([[0, 0, 0], [1000, 0, 0]], dtype=float)
    sky = np.array([0, 0, 1])
    times = audit.independent_times(positions, np.zeros(3), sky, 75)
    np.testing.assert_array_equal(times, [100_000, 100_075])
    times = audit.independent_times(positions, np.zeros(3), np.array([1, 0, 0]), 75)
    assert times[1] < times[0]
    assert times[0] - times[1] == pytest.approx(1000 / 0.299792458)


def test_32_actual_fits_obey_translation_and_rotation() -> None:
    result = audit.invariance_checks()
    assert len(result["fit_checks"]) == 32
    assert result["sign_and_reference_time_checks"] == "passed"


def test_output_json_refuses_overwrite_and_nonfinite(tmp_path) -> None:
    target = tmp_path / "first.json"
    audit.write_json(target, {"valid": 1})
    with pytest.raises(FileExistsError):
        audit.write_json(target, {"valid": 2})
    assert json.loads(target.read_text()) == {"valid": 1}
    with pytest.raises(ValueError):
        audit.write_json(tmp_path / "bad.json", {"invalid": float("nan")})


def test_existing_output_directory_rejected_before_reading_inputs(tmp_path) -> None:
    with pytest.raises(FileExistsError):
        audit.run(tmp_path / "absent_repository", tmp_path)


@pytest.mark.parametrize("bad", [[], [float("nan")], [float("inf")]])
def test_bad_summary_rejected(bad) -> None:
    with pytest.raises(ValueError):
        audit.distribution(bad)
