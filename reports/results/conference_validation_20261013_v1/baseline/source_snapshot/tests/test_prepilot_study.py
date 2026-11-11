"""Leakage and selection contract checks for the development experiment."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from auger_reco.evaluation import front_comparison, prepilot_study
from auger_reco.physics import plane_front, quadratic_front, signal_core


def test_signal_metadata_matches_ids_not_row_order():
    document = {
        "stations": [
            {"id": 8, "signal": 20.0, "dsignal": 2.0, "sat": 2},
            {"id": 3, "signal": 10.0, "dsignal": 1.0, "sat": 1},
            {"id": 5, "signal": 5.0, "dsignal": 0.5, "sat": 0},
        ]
    }
    result = prepilot_study.station_signal_metadata(document, np.array([5, 3, 8]))
    assert list(result.station_id) == [5, 3, 8]
    assert list(result.signal_vem) == [5, 10, 20]
    assert list(result.signal_eligible) == [True, True, False]
    assert "recovery_unknown" in result.iloc[2].signal_exclusion


@pytest.mark.parametrize(
    "field,value",
    [
        ("signal", -1),
        ("dsignal", 0),
        ("signal", True),
        ("dsignal", "2"),
        ("sat", None),
        ("sat", True),
        ("sat", 3),
    ],
)
def test_invalid_signal_metadata_recorded_not_silently_used(field, value):
    station = {"id": 1, "signal": 10.0, "dsignal": 1.0, "sat": 0, field: value}
    result = prepilot_study.station_signal_metadata({"stations": [station]}, [1])
    assert not result.iloc[0].signal_eligible
    assert result.iloc[0].signal_exclusion


def test_duplicate_id_fails():
    with pytest.raises(ValueError, match="unique"):
        prepilot_study.station_signal_metadata({"stations": [{"id": 1}, {"id": 1}]}, [1])


def test_signal_chain_excludes_held_out_time_and_signal():
    rng = np.random.default_rng(997)
    positions = rng.uniform(-1700, 1700, (14, 3))
    positions[:, 2] *= 0.01
    direction = plane_front.propagation_direction_from_angles(np.deg2rad(35), np.deg2rad(75))
    core = np.array([140.0, -230.0, 1.0])
    times = quadratic_front.quadratic_front_times_ns(positions, direction, core, 1e5, 80e-6)
    options = signal_core.SignalCoreFitOptions(-3, 1)
    signals = signal_core.predict_signals_vem(positions, direction, core, 100, options=options)
    data = SimpleNamespace(
        number_of_stations=14,
        station_positions_m=positions,
        observed_times_ns=times,
        timing_uncertainties_ns=np.ones(14) * 10,
    )
    metadata = pd.DataFrame(
        {"signal_eligible": True, "signal_vem": signals, "signal_uncertainty_vem": signals * 0.1}
    )
    keep = np.arange(14) != 0
    before = prepilot_study._signal_chain(data, core[2], metadata, options, keep)
    data.observed_times_ns = times.copy()
    data.observed_times_ns[0] += 1e7
    data.timing_uncertainties_ns[0] = 0.001
    metadata.loc[0, "signal_vem"] *= 1e6
    metadata.loc[0, "signal_uncertainty_vem"] *= 1e8
    after = prepilot_study._signal_chain(data, core[2], metadata, options, keep)
    np.testing.assert_array_equal(before[1].core_position_m, after[1].core_position_m)
    np.testing.assert_array_equal(before[2].sky_direction, after[2].sky_direction)
    predicted_before = front_comparison.predict_fit_times_ns(before[2], positions[:1])
    predicted_after = front_comparison.predict_fit_times_ns(after[2], positions[:1])
    np.testing.assert_array_equal(predicted_before, predicted_after)


def test_json_sanitizer_keeps_missing_distinct_from_zero():
    result = prepilot_study.json_safe({"missing": float("nan"), "value": np.float64(0)})
    assert result == {"missing": None, "value": 0.0}


@pytest.mark.parametrize(
    "flag",
    [
        "core_domain_boundary",
        "rank_deficient",
        "ill_conditioned",
        "multiple_near_equal_core_solutions",
    ],
)
def test_numerical_convergence_not_enough_for_signal_quality(flag):
    assert not prepilot_study.signal_numerical_quality_pass(["experimental_fixed_shape", flag])
    assert prepilot_study.signal_numerical_quality_pass(["experimental_fixed_shape"])


def test_handoff_exports_only_safe_columns_and_retains_splits(tmp_path, monkeypatch):
    source = tmp_path / "data/manifests/pilot_sd1500_vertical_v1.csv"
    source.parent.mkdir(parents=True)
    source.write_text("test manifest identity", encoding="utf-8")
    safe = [
        {
            "event_id": str(i).zfill(12),
            "split": "train" if i < 700 else "test",
            "forbidden_target": 123,
        }
        for i in range(1000)
    ]
    monkeypatch.setattr(prepilot_study.development_sample, "load_selection_rows", lambda _: safe)
    study = SimpleNamespace(root=tmp_path, output=tmp_path)
    contract = prepilot_study.freeze_pilot_handoff(study)
    execution = pd.read_csv(tmp_path / "pilot_execution_target_free.csv", dtype={"event_id": str})
    assert list(execution.columns) == ["event_id", "split", "release", "path"]
    assert len(execution) == 1000
    assert (execution.split == "test").sum() == 300
    assert not contract["pilot_executed"]
    assert not contract["signal_model_promoted"]
    assert contract["models"] == ["plane", "published_core_assisted_quadratic"]


def test_handoff_rejects_changed_cohort_size(tmp_path, monkeypatch):
    monkeypatch.setattr(prepilot_study.development_sample, "load_selection_rows", lambda _: [])
    with pytest.raises(RuntimeError, match="1000"):
        prepilot_study.freeze_pilot_handoff(SimpleNamespace(root=tmp_path, output=tmp_path))
