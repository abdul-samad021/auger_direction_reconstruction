"""Reproducible development-only diagnostics before freezing the larger pilot.

This runner does not download events, change timing selection, rescale errors,
or promote the experimental signal model. Every run gets a new output directory.
"""

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from auger_reco.data import core_reference, development_sample, event_json
from auger_reco.evaluation import direction_diagnostics, front_comparison
from auger_reco.physics import curved_front, plane_front, quadratic_front, signal_core

FOCUS_ID = "081847956000"
SEED = 20261011
TRIALS = 30
SLOPES = tuple((beta, gamma) for beta in (-2.5, -3.0, -3.5) for gamma in (0.0, 1.0))
DIRECTIONS = ((25.0, 20.0), (54.0, 54.0), (60.0, 210.0))
GENERATORS = ("plane", "quadratic", "sphere", "quadratic_coherent_gradient")
MODULES = (
    core_reference,
    development_sample,
    event_json,
    direction_diagnostics,
    front_comparison,
    curved_front,
    plane_front,
    quadratic_front,
    signal_core,
)
KNOWN_FAILURES = (
    plane_front.DegenerateStationGeometryError,
    plane_front.PlaneFrontInitializationError,
    plane_front.PlaneFrontOptimizationError,
    curved_front.QuadraticFrontGeometryError,
    curved_front.QuadraticFrontOptimizationError,
    signal_core.SignalCoreOptimizationError,
    ValueError,
    FloatingPointError,
    np.linalg.LinAlgError,
)


def json_safe(value):
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path, content):
    path.write_text(
        json.dumps(json_safe(content), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


@dataclass
class Study:
    root: Path
    previous: Path
    output: Path
    configuration: dict
    events: dict = field(default_factory=dict)

    def verify(self):
        for item in self.configuration["tracked_files"]:
            if digest(self.root / item["path"]) != item["sha256"]:
                raise RuntimeError(f"Input/source changed: {item['path']}. Start a new run.")


def station_signal_metadata(document, station_ids):
    """Join released measurements by ID; record rather than hide signal exclusions.

    Invalid signal metadata excludes a station only from the experimental signal
    likelihood, never from timing. No spDistance, core, energy or reference angle
    is read here. Invalid/duplicate identifiers are structural errors.
    """
    by_id = {}
    for station in document["stations"]:
        identifier = station.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier in by_id:
            raise ValueError("Station identifiers must be unique integers.")
        by_id[identifier] = station
    rows = []
    for identifier in station_ids:
        station = by_id[int(identifier)]
        values = {}
        reasons = []
        for key in ("signal", "dsignal"):
            value = station.get(key)
            valid = (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and np.isfinite(value)
                and value > 0
            )
            values[key] = float(value) if valid else np.nan
            if not valid:
                reasons.append(f"invalid_{key}")
        saturation = station.get("sat")
        valid_sat = isinstance(saturation, int) and not isinstance(saturation, bool)
        if not valid_sat or saturation not in (0, 1, 2):
            saturation = None
            reasons.append("unknown_saturation")
        elif saturation == 2:
            reasons.append("both_gains_saturated_recovery_unknown")
        rows.append(
            {
                "station_id": int(identifier),
                "signal_vem": values["signal"],
                "signal_uncertainty_vem": values["dsignal"],
                "saturation": saturation,
                "signal_eligible": not reasons,
                "signal_exclusion": ";".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def create_study(root: Path) -> Study:
    root = root.resolve()
    registry = json.loads((root / "reports/real_front_run_registry.json").read_text())
    previous = root / "reports/results" / registry["authoritative_run"]
    archived_hashes = json.loads((previous / "artifact_hashes.json").read_text())
    for relative, expected in archived_hashes.items():
        target = (previous / relative).resolve()
        if not target.is_relative_to(previous.resolve()) or digest(target) != expected:
            raise RuntimeError("Previous archived run failed its integrity check.")
    manifest_path = root / "data/manifests/real_front_development_v1.json"
    manifest = json.loads(manifest_path.read_text())
    pilot_path = root / "data/manifests/pilot_sd1500_vertical_v1.csv"
    if digest(pilot_path) != manifest["source_sha256"]:
        raise RuntimeError("Frozen pilot manifest changed.")
    rows = manifest["events"]
    ids = [str(row["event_id"]).zfill(12) for row in rows]
    if len(ids) != 20 or len(set(ids)) != 20 or ids[0] != FOCUS_ID:
        raise RuntimeError("Expected the original focus + 19 training events.")
    safe_rows = development_sample.load_selection_rows(pilot_path)
    regenerated = development_sample.select_development_events(safe_rows)
    if [row["event_id"] for row in regenerated] != ids[1:]:
        raise RuntimeError("Development selection changed.")
    if any(row["split"] != "train" for row in rows[1:]):
        raise RuntimeError("Protected event in development experiment.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    output = root / "reports/results" / f"prepilot_diagnostics_{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources").mkdir()
    paths = [Path(module.__file__).resolve() for module in MODULES] + [Path(__file__).resolve()]
    if any(not path.is_relative_to(root / "src") for path in paths):
        raise RuntimeError("Imported another project installation.")
    paths += [
        manifest_path,
        pilot_path,
        root / "docs/prepilot_diagnostics_protocol.md",
        root / "notebooks/07_pre_pilot_diagnostics.ipynb",
    ]
    config = {
        "seed": SEED,
        "trials_per_case": TRIALS,
        "directions_deg": DIRECTIONS,
        "generators": GENERATORS,
        "signal_slopes": SLOPES,
        "previous_run": str(previous.relative_to(root)),
        "event_ids": ids,
        "created_at": datetime.now(UTC).isoformat(),
        "pilot_started": False,
        "packages": {name: version(name) for name in ("numpy", "scipy", "pandas")},
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=root, text=True),
        "tracked_files": [],
        "signal_options": [],
        "plane_options": asdict(plane_front.PlaneFrontFitOptions()),
        "quadratic_options": asdict(curved_front.QuadraticFrontFitOptions()),
    }
    for beta, gamma in SLOPES:
        config["signal_options"].append(asdict(signal_core.SignalCoreFitOptions(beta, gamma)))
    previous_hashes = json.loads((previous / "input_file_sha256.json").read_text())
    study = Study(root, previous, output, config)
    for identifier in ids:
        path = root / "data/raw/events" / f"Auger_{identifier}.json"
        if digest(path) != previous_hashes[identifier]:
            raise RuntimeError(f"Event changed since previous audited run: {identifier}")
        measurements = event_json.load_auger_plane_front_input(path, minimum_stations=7)
        core = core_reference.load_auger_core_reference(path)
        reference = event_json.load_auger_direction_reference(path)
        identities = {
            (item.event_id, item.embedded_release, item.format_version)
            for item in (measurements, core, reference)
        }
        if len(identities) != 1 or measurements.canonical_event_id != identifier:
            raise RuntimeError("Input metadata mismatch.")
        metadata = station_signal_metadata(json.loads(path.read_text()), measurements.station_ids)
        study.events[identifier] = (measurements, core, reference, metadata)
        paths.append(path)
    # Snapshot dependencies and previous artifact hashes; never overwrite that run.
    previous_receipt = previous / "artifact_hashes.json"
    paths.append(previous_receipt)
    for name in (
        "all_fit_records_before_reference.csv",
        "all_station_residuals.csv",
        "heldout_summary.csv",
    ):
        paths.append(previous / name)
    for index, path in enumerate(paths):
        config["tracked_files"].append(
            {"path": str(path.relative_to(root)), "sha256": digest(path)}
        )
        if path.suffix in (".py", ".md", ".ipynb"):
            shutil.copy2(path, output / "sources" / f"{index:02}_{path.name}")
    write_json(output / "configuration.json", config)
    write_json(output / "run_status.json", {"state": "running", "pilot_started": False})
    return study


def run_reference_and_influence(study: Study):
    """Read prior fits and add fixed-direction profiles, never retune the reference."""
    study.verify()
    old = pd.read_csv(
        study.previous / "all_fit_records_before_reference.csv", dtype={"event_id": str}
    )
    residual = pd.read_csv(study.previous / "all_station_residuals.csv", dtype={"event_id": str})
    rows, station_rows, influence_rows = [], [], []
    for identifier, (data, core, reference, metadata) in study.events.items():
        direction = plane_front.propagation_direction_from_angles(
            np.deg2rad(reference.zenith_deg), np.deg2rad(reference.azimuth_deg)
        )
        for weighting in ("timing", "uniform"):
            fit = direction_diagnostics.fit_fixed_direction_quadratic(
                data.station_positions_m,
                data.observed_times_ns,
                data.timing_uncertainties_ns,
                core.position_m,
                direction,
                weighting=weighting,
            )
            baseline = old.loc[
                (old.event_id == identifier)
                & (old.stage == "full")
                & (old.model == "quadratic")
                & (old.weighting == weighting)
            ].iloc[0]
            delta = fit.objective_sum_squares - baseline.objective_sum_squares
            if delta < -max(1e-4, 1e-7 * baseline.objective_sum_squares):
                raise RuntimeError(
                    "Fixed direction improved free-direction optimum; investigate seeds."
                )
            rows.append(
                {
                    "event_id": identifier,
                    "weighting": weighting,
                    "free_chi_square": baseline.chi_square,
                    "fixed_reference_chi_square": fit.chi_square,
                    "delta_objective": delta,
                    "fixed_delay_at_1km_ns": fit.delay_at_1km_ns,
                    "fixed_rms_ns": fit.rms_residual_ns,
                    "free_rms_ns": baseline.rms_residual_ns,
                    "fixed_nominal_reduced_chi_square": fit.reduced_chi_square,
                    "fixed_nominal_dof": fit.nominal_degrees_of_freedom,
                    "curvature_at_boundary": fit.curvature_at_boundary,
                }
            )
            for index, station_id in enumerate(data.station_ids):
                station_rows.append(
                    {
                        "event_id": identifier,
                        "weighting": weighting,
                        "station_id": int(station_id),
                        "fixed_reference_residual_ns": fit.residuals_ns[index],
                        "fixed_reference_q": fit.standardized_residuals[index],
                    }
                )
        folds = old.loc[
            (old.event_id == identifier)
            & (old.stage == "leave_one_out")
            & (old.model == "quadratic")
            & (old.weighting == "timing")
        ].copy()
        folds["station_id"] = folds.held_out_station_id.astype(int)
        held = residual.loc[
            (residual.event_id == identifier)
            & (residual.stage == "leave_one_out")
            & (residual.model == "quadratic")
            & (residual.weighting == "timing")
        ]
        joined = folds.merge(metadata, on="station_id", validate="one_to_one").merge(
            held[
                [
                    "station_id",
                    "residual_ns",
                    "residual_over_observed_sigma",
                    "timing_uncertainty_ns",
                    "axis_distance_m",
                ]
            ],
            on="station_id",
            how="left",
            validate="one_to_one",
        )
        influence_rows.extend(joined.to_dict("records"))
    profiles = pd.DataFrame(rows)
    profiles.to_csv(study.output / "fixed_reference_profiles.csv", index=False)
    pd.DataFrame(station_rows).to_csv(
        study.output / "fixed_reference_station_residuals.csv", index=False
    )
    influence = pd.DataFrame(influence_rows)
    influence.to_csv(study.output / "station_influence.csv", index=False)
    metadata = pd.concat(
        [
            frame.assign(event_id=identifier)
            for identifier, (_, _, _, frame) in study.events.items()
        ],
        ignore_index=True,
    )
    metadata.to_csv(study.output / "signal_selection.csv", index=False)
    full = residual.loc[
        (residual.stage == "full")
        & (residual.model == "quadratic")
        & (residual.weighting == "timing")
    ].merge(metadata, on=["event_id", "station_id"], validate="one_to_one")
    full.to_csv(study.output / "timing_residual_signal_diagnostics.csv", index=False)
    summaries = []
    for identifier, frame in influence.groupby("event_id", sort=False):
        peak = frame.loc[frame.direction_shift_from_full_deg.idxmax()]
        summaries.append(
            {
                "event_id": identifier,
                "folds": len(frame),
                "successful_folds": int(frame.success.sum()),
                "maximum_direction_shift_deg": peak.direction_shift_from_full_deg,
                "most_influential_station": int(peak.station_id),
                "heldout_rms_ns": np.sqrt(np.mean(frame.residual_ns**2)),
                "heldout_normalized_mse": np.mean(frame.residual_over_observed_sigma**2),
            }
        )
    influence_summary = pd.DataFrame(summaries)
    influence_summary.to_csv(study.output / "influence_summary.csv", index=False)
    return profiles, influence_summary


def _signal_chain(data, core_z, metadata, options, keep=None):
    n = data.number_of_stations
    keep = np.ones(n, dtype=bool) if keep is None else keep
    signal_mask = metadata.signal_eligible.to_numpy(dtype=bool) & keep
    p, t, s = data.station_positions_m, data.observed_times_ns, data.timing_uncertainties_ns
    plane = plane_front.fit_plane_front(p[keep], t[keep], s[keep])
    signal = signal_core.fit_signal_core(
        p[signal_mask],
        metadata.signal_vem.to_numpy()[signal_mask],
        metadata.signal_uncertainty_vem.to_numpy()[signal_mask],
        propagation_direction=plane.propagation_direction,
        core_z_m=core_z,
        options=options,
    )
    curve = curved_front.fit_quadratic_front(
        p[keep], t[keep], s[keep], core_position_m=signal.core_position_m
    )
    return plane, signal, curve


def signal_numerical_quality_pass(flags):
    """Convergence is not validity: expose boundary/degenerate core solutions."""
    invalid = {
        "rank_deficient",
        "ill_conditioned",
        "core_domain_boundary",
        "multiple_near_equal_core_solutions",
    }
    return not (set(flags) & invalid)


def run_signal_experiment(study: Study):
    """Record all slope settings and paired held-out predictions for the central one."""
    study.verify()
    records, folds, attempts = [], [], []
    for identifier, (data, core, reference, metadata) in study.events.items():
        for beta, gamma in SLOPES:
            context = {
                "event_id": identifier,
                "beta": beta,
                "gamma": gamma,
                "signal_stations": int(metadata.signal_eligible.sum()),
                "timing_stations": data.number_of_stations,
            }
            options = signal_core.SignalCoreFitOptions(beta, gamma)
            try:
                _, signal, curve = _signal_chain(data, float(core.position_m[2]), metadata, options)
            except KNOWN_FAILURES as error:
                records.append(
                    {
                        **context,
                        "success": False,
                        "failure_type": type(error).__name__,
                        "failure_message": str(error),
                    }
                )
                attempts.append({**context, "attempts": getattr(error, "attempts", ())})
            else:
                reference_sky = plane_front.sky_direction_from_angles(
                    np.deg2rad(reference.zenith_deg), np.deg2rad(reference.azimuth_deg)
                )
                records.append(
                    {
                        **context,
                        "success": True,
                        "core_x_m": signal.core_position_m[0],
                        "core_y_m": signal.core_position_m[1],
                        "core_horizontal_separation_from_reference_m": np.linalg.norm(
                            (signal.core_position_m - core.position_m)[:2]
                        ),
                        "s1000_vem": signal.s1000_vem,
                        "signal_surrogate_objective": signal.objective_sum_squares,
                        "signal_condition_number": signal.final_jacobian_condition_number,
                        "signal_rank": signal.final_jacobian_rank,
                        "signal_numerical_quality_pass": signal_numerical_quality_pass(
                            signal.quality_flags
                        ),
                        "signal_flags": ";".join(signal.quality_flags),
                        "timing_nominal_reduced_chi_square": curve.reduced_chi_square,
                        "timing_rms_ns": curve.rms_residual_ns,
                        "delay_at_1km_ns": curve.delay_at_1km_ns,
                        "reference_separation_deg": plane_front.angular_separation_deg(
                            curve.sky_direction, reference_sky
                        ),
                    }
                )
                attempts.append(
                    {
                        **context,
                        "signal_attempts": signal.optimizer_attempts,
                        "timing_attempts": [asdict(a) for a in curve.optimizer_attempts],
                    }
                )
        # In each fold refit direction AND signal core without the held-out time
        # or signal. Full-event selected-station status and official core z remain.
        for index, station_id in enumerate(data.station_ids):
            keep = np.arange(data.number_of_stations) != index
            context = {
                "event_id": identifier,
                "station_id": int(station_id),
                "beta": -3.0,
                "gamma": 1.0,
            }
            try:
                _, signal, curve = _signal_chain(
                    data,
                    float(core.position_m[2]),
                    metadata,
                    signal_core.SignalCoreFitOptions(-3, 1),
                    keep,
                )
                prediction = float(
                    front_comparison.predict_fit_times_ns(
                        curve, data.station_positions_m[index : index + 1]
                    )[0]
                )
                error = data.observed_times_ns[index] - prediction
                folds.append(
                    {
                        **context,
                        "success": True,
                        "predicted_time_ns": prediction,
                        "signal_numerical_quality_pass": signal_numerical_quality_pass(
                            signal.quality_flags
                        ),
                        "residual_ns": error,
                        "residual_over_observed_sigma": error / data.timing_uncertainties_ns[index],
                        "signal_flags": ";".join(signal.quality_flags),
                    }
                )
            except KNOWN_FAILURES as error:
                folds.append(
                    {
                        **context,
                        "success": False,
                        "failure_type": type(error).__name__,
                        "failure_message": str(error),
                    }
                )
        print(f"Signal/core study: {identifier} complete", flush=True)
        write_json(study.output / "signal_optimizer_attempts.json", attempts)
        pd.DataFrame(records).to_csv(study.output / "signal_core_models.csv", index=False)
        pd.DataFrame(folds).to_csv(study.output / "signal_core_heldout.csv", index=False)
    return pd.DataFrame(records), pd.DataFrame(folds)


def freeze_pilot_handoff(study: Study):
    """Export a target-free execution list and fixed baseline-only analysis contract.

    Only safe selection columns are loaded. No protected reference is inspected
    or exported. A future runner must save predictions before loading targets.
    This prepares that run; it does not execute it or promote the signal model.
    """
    source = study.root / "data/manifests/pilot_sd1500_vertical_v1.csv"
    safe = development_sample.load_selection_rows(source)
    ids = [str(row["event_id"]).zfill(12) for row in safe]
    if len(ids) != 1000 or len(set(ids)) != 1000:
        raise RuntimeError("Expected exactly the existing 1000 unique pilot identifiers.")
    execution = pd.DataFrame(
        [
            {
                "event_id": identifier,
                "split": row["split"],
                "release": "3",
                "path": f"data/raw/events/Auger_{identifier}.json",
            }
            for identifier, row in zip(ids, safe, strict=True)
        ]
    )
    execution.to_csv(study.output / "pilot_execution_target_free.csv", index=False)
    contract = {
        "version": 1,
        "status": "frozen_baseline_comparison_only",
        "pilot_executed": False,
        "original_manifest_sha256": digest(source),
        "execution_manifest_sha256": digest(study.output / "pilot_execution_target_free.csv"),
        "event_count": 1000,
        "models": ["plane", "published_core_assisted_quadratic"],
        "weightings": ["timing", "uniform"],
        "plane_options": asdict(plane_front.PlaneFrontFitOptions()),
        "quadratic_options": asdict(curved_front.QuadraticFrontFitOptions()),
        "selection": "auger_isSelected",
        "uncertainty_rescaling": False,
        "residual_station_rejection": False,
        "earth_curvature_correction": "none_added",
        "signal_model_promoted": False,
        "fixed_reference_direction_fit_in_pilot": False,
        "reference_access": "only after complete per-event predictions are persisted and hashed",
        "failure_policy": "retain every event/fit; no replacement or silent fallback",
        "quality_policy": "retain all solver and geometry flags; convergence is not validity",
        "heldout_policy": "refit every station; <6 retained stations is explicit quadratic failure",
        "influence_warning_deg": 1.0,
        "influence_warning_action": "report only; never exclude from primary aggregates",
        "reporting": [
            "failure denominators",
            "flagged event counts",
            "per-event timing RMS",
            "nominal reduced chi-square",
            "conditional heldout RMS and normalized MSE",
            "maximum leave-one-station-out direction change",
            "reference separation",
            "median, p68 and p95 per-event metrics by split and multiplicity",
        ],
        "pairing": "paired complete events, with incomplete counts also reported",
        "claim_limits": "reference agreement, not true-direction accuracy or superiority to Auger",
        "data_dependence": "official selection/core; development used only train plus old focus",
        "future_ml_test_split": "remains unavailable to model development and tuning",
        "execution_stages": "train analysis first; protected predictions/references stay sealed",
        "protected_evaluation": "after full-procedure freeze only; never feed results into tuning",
    }
    write_json(study.output / "pilot_baseline_contract.json", contract)
    return contract


def run_timing_controls(study: Study):
    """Paired simulations with known directions; include model-mismatch cases."""
    study.verify()
    data = study.events[FOCUS_ID][0]
    base = data.station_positions_m - data.station_positions_m.mean(axis=0)
    sigma = data.timing_uncertainties_ns
    rows = []
    for geometry_index, geometry in enumerate(("measured_3d", "flattened")):
        positions = base.copy()
        if geometry == "flattened":
            positions[:, 2] = 0
        core = np.array([150.0, -100.0, 0.0])
        for direction_index, (zenith, azimuth) in enumerate(DIRECTIONS):
            direction = plane_front.propagation_direction_from_angles(
                np.deg2rad(zenith), np.deg2rad(azimuth)
            )
            rng = np.random.default_rng(
                np.random.SeedSequence([SEED, geometry_index, direction_index])
            )
            noises = np.vstack((np.zeros(len(sigma)), rng.normal(0, sigma, (TRIALS, len(sigma)))))
            for generator in GENERATORS:
                if generator == "sphere":
                    exact = direction_diagnostics.spherical_front_times_ns(
                        positions, direction, core, 1e5, 1 / (2 * plane_front.C_M_PER_NS * 100e-6)
                    )
                else:
                    delay = 0 if generator == "plane" else 100e-6
                    exact = quadratic_front.quadratic_front_times_ns(
                        positions, direction, core, 1e5, delay
                    )
                    if generator == "quadratic_coherent_gradient":
                        exact += 100 * positions[:, 0] / 1000
                for trial, noise in enumerate(noises):
                    for model in ("plane", "quadratic_true_core", "quadratic_shifted_core"):
                        context = {
                            "geometry": geometry,
                            "zenith_true_deg": zenith,
                            "azimuth_true_deg": azimuth,
                            "generator": generator,
                            "trial": trial - 1,
                            "noise_free": trial == 0,
                            "model": model,
                        }
                        try:
                            if model == "plane":
                                fit = plane_front.fit_plane_front(positions, exact + noise, sigma)
                            else:
                                fit_core = core + (
                                    [100, 0, 0] if model.endswith("shifted_core") else 0
                                )
                                fit = curved_front.fit_quadratic_front(
                                    positions, exact + noise, sigma, core_position_m=fit_core
                                )
                            rows.append(
                                {
                                    **context,
                                    "success": True,
                                    "angular_error_deg": plane_front.angular_separation_deg(
                                        fit.propagation_direction, direction
                                    ),
                                    "nominal_reduced_chi_square": fit.reduced_chi_square,
                                    "rms_ns": fit.rms_residual_ns,
                                    "quality_flags": ";".join(fit.quality_flags),
                                }
                            )
                        except KNOWN_FAILURES as error:
                            rows.append(
                                {
                                    **context,
                                    "success": False,
                                    "failure_type": type(error).__name__,
                                    "failure_message": str(error),
                                }
                            )
                print(f"Timing controls: {geometry}, {zenith}/{azimuth}, {generator}", flush=True)
                pd.DataFrame(rows).to_csv(study.output / "timing_controls.csv", index=False)
    results = pd.DataFrame(rows)
    # Every fixed case stays separate: do not pool noise draws as real events.
    keys = ["geometry", "zenith_true_deg", "azimuth_true_deg", "generator", "model"]
    summary = (
        results.loc[~results.noise_free]
        .groupby(keys, sort=False)
        .agg(
            attempted=("success", "size"),
            successful=("success", "sum"),
            median_error_deg=("angular_error_deg", "median"),
            mean_nominal_reduced_chi_square=("nominal_reduced_chi_square", "mean"),
        )
    )
    summary.to_csv(study.output / "timing_control_summary.csv")
    return results, summary.reset_index()


def run_signal_controls(study: Study):
    """Known-truth end-to-end signal-core controls with correct and wrong LDF shape."""
    study.verify()
    base = study.events[FOCUS_ID][0]
    positions = base.station_positions_m - base.station_positions_m.mean(axis=0)
    core = np.array([150.0, -100.0, 0.0])
    fit_options = signal_core.SignalCoreFitOptions(-3, 1)
    records = []
    for case, (zenith, azimuth) in enumerate(DIRECTIONS[:2]):
        direction = plane_front.propagation_direction_from_angles(
            np.deg2rad(zenith), np.deg2rad(azimuth)
        )
        exact_time = quadratic_front.quadratic_front_times_ns(
            positions, direction, core, 1e5, 100e-6
        )
        rng = np.random.default_rng(np.random.SeedSequence([SEED, 100, case]))
        timing_noises = rng.normal(0, base.timing_uncertainties_ns, (TRIALS, len(positions)))
        log_noises = rng.normal(0, np.sqrt(np.log1p(0.15**2)), (TRIALS, len(positions)))
        for shape, truth_options in (
            ("matched", fit_options),
            ("mismatched", signal_core.SignalCoreFitOptions(-2.5, 0)),
        ):
            exact_signal = signal_core.predict_signals_vem(
                positions, direction, core, 100, options=truth_options
            )
            for trial in range(TRIALS):
                observed = exact_time + timing_noises[trial]
                signal = exact_signal * np.exp(log_noises[trial])
                context = {
                    "zenith_true_deg": zenith,
                    "azimuth_true_deg": azimuth,
                    "shape": shape,
                    "trial": trial,
                }
                try:
                    plane = plane_front.fit_plane_front(
                        positions, observed, base.timing_uncertainties_ns
                    )
                    estimated = signal_core.fit_signal_core(
                        positions,
                        signal,
                        0.15 * signal,
                        propagation_direction=plane.propagation_direction,
                        core_z_m=0,
                        options=fit_options,
                    )
                    fit = curved_front.fit_quadratic_front(
                        positions,
                        observed,
                        base.timing_uncertainties_ns,
                        core_position_m=estimated.core_position_m,
                    )
                    known_core = curved_front.fit_quadratic_front(
                        positions, observed, base.timing_uncertainties_ns, core_position_m=core
                    )
                    records.append(
                        {
                            **context,
                            "success": True,
                            "core_error_m": np.linalg.norm(estimated.core_position_m - core),
                            "angular_error_deg": plane_front.angular_separation_deg(
                                fit.propagation_direction, direction
                            ),
                            "known_core_angular_error_deg": plane_front.angular_separation_deg(
                                known_core.propagation_direction, direction
                            ),
                            "nominal_reduced_chi_square": fit.reduced_chi_square,
                            "quality_flags": ";".join(estimated.quality_flags),
                        }
                    )
                except KNOWN_FAILURES as error:
                    records.append(
                        {
                            **context,
                            "success": False,
                            "failure_type": type(error).__name__,
                            "failure_message": str(error),
                        }
                    )
    results = pd.DataFrame(records)
    results.to_csv(study.output / "signal_controls.csv", index=False)
    return results


def summarize_signal_heldout(study: Study, folds):
    """Compare only complete paired events, with all failure denominators visible."""
    summaries = []
    for identifier, group in folds.groupby("event_id", sort=False):
        good = group.loc[group.success]
        complete = len(good) == len(group)
        summaries.append(
            {
                "event_id": identifier,
                "expected_folds": len(group),
                "successful_folds": len(good),
                "complete": complete,
                "signal_core_rms_ns": np.sqrt(np.mean(good.residual_ns**2)) if complete else np.nan,
                "signal_core_normalized_mse": np.mean(good.residual_over_observed_sigma**2)
                if complete
                else np.nan,
            }
        )
    result = pd.DataFrame(summaries)
    previous = pd.read_csv(study.previous / "heldout_summary.csv", dtype={"event_id": str})
    previous = previous.loc[(previous.model == "quadratic") & (previous.weighting == "timing")]
    result = result.merge(
        previous[["event_id", "heldout_rms_ns", "heldout_mean_squared_normalized_error"]],
        on="event_id",
        validate="one_to_one",
    )
    result.to_csv(study.output / "signal_core_heldout_summary.csv", index=False)
    return result


def make_figures(study: Study, profiles, influence, signals, timing_summary, signal_controls):
    """Fixed scales/labels; do not omit adverse development events from figures."""
    import matplotlib.pyplot as plt

    files = []

    def save(fig, name):
        path = study.output / name
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        files.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    points = profiles.loc[profiles.weighting == "timing"]
    axes[0].scatter(
        points.free_chi_square, points.fixed_reference_chi_square, label="20 development events"
    )
    focus = points.loc[points.event_id == FOCUS_ID]
    axes[0].scatter(
        focus.free_chi_square, focus.fixed_reference_chi_square, c="tab:red", label="Focus event"
    )
    low = min(points.free_chi_square.min(), points.fixed_reference_chi_square.min()) * 0.8
    high = max(points.free_chi_square.max(), points.fixed_reference_chi_square.max()) * 1.2
    axes[0].plot([low, high], [low, high], color="gray", ls="--")
    axes[0].set(
        xscale="log",
        yscale="log",
        xlabel="Free-direction quadratic chi-square",
        ylabel="Fixed Auger-direction chi-square",
        title="Same stations, uncertainties and fixed core",
    )
    axes[0].legend(fontsize=8)
    ranked = influence.sort_values("maximum_direction_shift_deg")
    axes[1].barh(ranked.event_id, ranked.maximum_direction_shift_deg)
    axes[1].set(
        xlabel="Maximum leave-one-station-out direction shift (deg)",
        title="Influence: every development event",
    )
    axes[1].tick_params(axis="y", labelsize=7)
    save(fig, "reference_and_station_influence.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    focus = signals.loc[(signals.event_id == FOCUS_ID) & signals.success]
    for _, row in focus.iterrows():
        label = f"beta={row.beta:g}, gamma={row.gamma:g}"
        axes[0].scatter(row.core_x_m, row.core_y_m, label=label)
        axes[1].scatter(row.timing_nominal_reduced_chi_square, row.reference_separation_deg)
        axes[1].annotate(
            f"{row.beta:g}/{row.gamma:g}",
            (row.timing_nominal_reduced_chi_square, row.reference_separation_deg),
            fontsize=8,
        )
    core = study.events[FOCUS_ID][1].position_m
    axes[0].scatter(
        core[0], core[1], marker="*", s=130, color="black", label="Auger reference core"
    )
    axes[0].set(
        xlabel="Core x (m)",
        ylabel="Core y (m)",
        title="Signal-core shape sensitivity; not confidence contours",
    )
    axes[0].legend(fontsize=7)
    axes[1].set(
        xlabel="Conditional nominal reduced timing chi-square",
        ylabel="Separation from Auger direction (deg)",
        title="All six signal-shape settings; no winner selected",
    )
    save(fig, "signal_core_sensitivity.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for offset, model in enumerate(("plane", "quadratic_true_core", "quadratic_shifted_core")):
        frame = timing_summary.loc[timing_summary.model == model]
        # Each point is the median across the six case-level summary values,
        # not an event-population accuracy or a confidence interval.
        medians = frame.groupby("generator").median(numeric_only=True).reindex(GENERATORS)
        x = np.arange(len(GENERATORS)) + (offset - 1) * 0.22
        axes[0].bar(x, medians.median_error_deg, width=0.22, label=model)
        axes[1].bar(x, medians.mean_nominal_reduced_chi_square, width=0.22, label=model)
    for axis in axes:
        axis.set_xticks(
            np.arange(4), ["Plane", "Quadratic", "Sphere", "Quadratic +\ntiming gradient"]
        )
    axes[0].set(
        ylabel="Median of six case-median angular errors (deg)", title="Known-truth timing controls"
    )
    axes[1].set(
        ylabel="Median of six case-mean nominal reduced chi-square",
        title="Good timing fit does not guarantee correct direction",
    )
    axes[1].axhline(1, color="black", ls="--", lw=1)
    axes[0].legend(fontsize=7)
    save(fig, "known_truth_timing_controls.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for shape, frame in signal_controls.groupby("shape", sort=False):
        axes[0].scatter(frame.core_error_m, frame.angular_error_deg, alpha=0.65, label=shape)
        axes[1].scatter(
            frame.nominal_reduced_chi_square, frame.angular_error_deg, alpha=0.65, label=shape
        )
    axes[0].set(
        xlabel="Known synthetic core error (m)",
        ylabel="True angular error (deg)",
        title="Signal-core + timing chain, 120 paired toy cases",
    )
    axes[1].set(
        xlabel="Conditional nominal reduced timing chi-square",
        ylabel="True angular error (deg)",
        title="Fixed signal shape: matched and mismatched generators",
    )
    axes[0].legend()
    save(fig, "known_truth_signal_controls.png")
    return files


def finish_study(
    study: Study, profiles, influence, signals, folds, timing, timing_summary, signal_controls
):
    """Write measured conclusions, explicit limitations and a conservative pilot gate."""
    study.verify()
    exact = timing.loc[
        timing.noise_free
        & timing.generator.isin(["plane", "quadratic"])
        & (timing.model == "quadratic_true_core")
    ]
    if not exact.success.all() or (exact.angular_error_deg > 1e-6).any():
        raise RuntimeError("Matched noiseless timing recovery failed; pilot gate closed.")
    freeze_pilot_handoff(study)
    heldout = summarize_signal_heldout(study, folds)
    files = make_figures(study, profiles, influence, signals, timing_summary, signal_controls)
    focus = profiles.loc[(profiles.event_id == FOCUS_ID) & (profiles.weighting == "timing")].iloc[0]
    focus_signal = signals.loc[(signals.event_id == FOCUS_ID) & signals.success]
    focus_influence = influence.loc[influence.event_id == FOCUS_ID].iloc[0]
    complete = heldout.loc[heldout.complete]
    wins = int(
        (complete.signal_core_normalized_mse < complete.heldout_mean_squared_normalized_error).sum()
    )
    numerical_pass = int(signals.signal_numerical_quality_pass.fillna(False).sum())
    boundary_rows = signals.loc[
        signals.signal_flags.fillna("").str.contains("core_domain_boundary")
    ]
    gradient = timing_summary.loc[
        (timing_summary.generator == "quadratic_coherent_gradient")
        & (timing_summary.model == "quadratic_true_core")
    ]
    summary_rows = []
    for (shape, zenith), group in signal_controls.groupby(["shape", "zenith_true_deg"]):
        summary_rows.append(
            {
                "shape": shape,
                "zenith_deg": zenith,
                "attempted": len(group),
                "successful": int(group.success.sum()),
                "median_core_error_m": group.core_error_m.median(),
                "median_angular_error_deg": group.angular_error_deg.median(),
                "median_known_core_angular_error_deg": group.known_core_angular_error_deg.median(),
            }
        )
    pd.DataFrame(summary_rows).to_csv(study.output / "signal_control_summary.csv", index=False)
    conclusion = f"""# Pre-pilot diagnostic results

Run: `{study.output.name}`. Previous run remains immutable. Only the original
focus and 19 preselected training events were used. No protected validation/test
events and no 1,000-event run were processed.

## Fixed reference direction

For the focus event, the free-direction timing-weighted quadratic chi-square is
{focus.free_chi_square:.6f}. Holding Auger's published SD direction fixed and
refitting core time plus curvature gives {focus.fixed_reference_chi_square:.6f};
the objective penalty is {focus.delta_objective:.6f}. The timing RMS changes from
{focus.free_rms_ns:.3f} to {focus.fixed_rms_ns:.3f} ns. Fixed-direction curvature
delay at 1 km is {focus.fixed_delay_at_1km_ns:.3f} ns.

This is a reference-conditioned diagnostic, not blind validation or proof that
either direction is true. No naive delta-chi-square significance is assigned.
Full results for both weighting modes and all 20 events are preserved.

## Station influence

The largest focus-event leave-one-station-out direction change is
{focus_influence.maximum_direction_shift_deg:.6f} degrees, at station
{int(focus_influence.most_influential_station)}. Complete fold-level direction
changes, residuals, signal, dsignal and saturation metadata are retained in
`station_influence.csv`; `influence_summary.csv` includes every event. Nothing
was rejected or reweighted using these diagnostics.

## Signal/core experiment — not a promoted reconstruction

Of {len(signals)} fixed-shape real-event models, {int(signals.success.sum())}
converged numerically; only {numerical_pass} passed the recorded numerical/core
quality checks. {len(boundary_rows)} reached a core-domain boundary. Convergence
must not be described as a valid physical reconstruction. All six uncalibrated
beta/gamma settings are reported. For the focus
event their estimated x/y cores are separated from the Auger core by
{focus_signal.core_horizontal_separation_from_reference_m.min():.2f} to
{focus_signal.core_horizontal_separation_from_reference_m.max():.2f} metres.
The corresponding reference-direction separations range from
{focus_signal.reference_separation_deg.min():.6f} to
{focus_signal.reference_separation_deg.max():.6f} degrees. These ranges are
sensitivity results, not uncertainty intervals and not a search for a winner.

For the preregistered central shape (beta=-3, gamma=1), the full chain was
refitted without each held-out station's time AND signal. {int(folds.success.sum())}
of {len(folds)} folds succeeded; {len(complete)} of 20 events have complete folds.
Its held-out normalized timing MSE improved on the published-core-assisted
quadratic baseline in {wins}/{len(complete)} complete events. Both methods retain
official station selection and published core z; baseline additionally inherits
the full-event x/y core. This is not independent end-to-end detector validation.

The signal objective is a fixed observed-log-error surrogate, not Auger's full
likelihood. Missing non-triggered-detector status, saturation recovery flags,
calibrated slope dependence and signal asymmetry prohibit promotion of this
model based solely on smaller residuals or reference separation. `sat=2` stations
were excluded from signal fitting only; their timing rows were unchanged.

## Controlled truth tests

Timing controls: {int(timing.success.sum())}/{len(timing)} fits succeeded over
two geometries, three directions, four generators and three fitting methods,
with 30 paired noise realizations plus one noise-free check per case. The exact
expanding sphere uses an independent distance formula; the coherent-gradient
case tests a systematic that can shift direction while leaving a small residual.
All cases and failures are reported, not just matched-model recovery.

For the coherent-gradient generator, the median across six case-median angular
errors of the true-core quadratic fit is {gradient.median_error_deg.median():.4f}
degrees, while the median across their mean nominal reduced chi-squares is
{gradient.mean_nominal_reduced_chi_square.median():.4f}. This is a controlled
counterexample to treating chi-square near one as proof of directional accuracy.
It is not evidence that this particular systematic exists in the Auger data.

Signal controls: {int(signal_controls.success.sum())}/{len(signal_controls)}
end-to-end toy chains succeeded at two directions with matched/mismatched lateral
shapes. These are controlled station-level toys, not realistic air-shower and
detector Monte Carlo. Synthesis truth never enters the tested chain's direction
or horizontal-core estimation. Known core z and generated uncertainties do.

## Pilot release decision

**The experimental signal-core estimator is not promoted.** Retain the tested
plane and explicitly published-core-assisted quadratic baselines. Do not replace
the core or tune beta/gamma using the published direction. Do not force nominal
reduced chi-square to one by clipping stations or scaling uncertainties.

The exact baseline settings and failure/reporting policy are now frozen in
`pilot_baseline_contract.json`, with a target-free 1000-row execution list in
`pilot_execution_target_free.csv`. That is readiness for a **labelled baseline
comparison**, not a certification of a solved or independent reconstruction.
The next batch implementation must enforce that contract, checkpoint failures,
and preserve protected splits. No protected outcomes are exposed for tuning;
the future ML test split must not become a development set. Lower timing
objectives alone cannot certify more accurate physical directions.

Primary sources: https://opendata.auger.org/data.php and
https://arxiv.org/abs/2007.09035 (especially Sections 5.1–5.2).
"""
    (study.output / "scientific_conclusion.md").write_text(conclusion, encoding="utf-8")
    write_json(
        study.output / "run_status.json",
        {
            "state": "complete",
            "pilot_started": False,
            "signal_model_promoted": False,
            "fixed_direction_fits": len(profiles),
            "real_signal_model_attempts": len(signals),
            "signal_heldout_attempts": len(folds),
            "timing_control_attempts": len(timing),
            "signal_control_attempts": len(signal_controls),
        },
    )
    hashes = {
        str(path.relative_to(study.output)): digest(path)
        for path in sorted(study.output.rglob("*"))
        if path.is_file()
    }
    write_json(study.output / "artifact_hashes.json", hashes)
    return conclusion, files, heldout
