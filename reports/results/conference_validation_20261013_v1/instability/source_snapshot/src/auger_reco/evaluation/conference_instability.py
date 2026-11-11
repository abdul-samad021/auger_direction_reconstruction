"""Training-only, frozen-case numerical and physical stability investigation.

The public fitter is left unchanged. An independent variable-projection solve
eliminates time and nonnegative curvature before optimizing direction. Its
agreement with the public four-parameter fit is a numerical cross-check, not
proof of a global optimum or accuracy on unknown real-event truth.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

from auger_reco.data import core_reference, event_json
from auger_reco.physics import curved_front, plane_front

type FloatArray = NDArray[np.float64]

BASELINE = Path("reports/results/training_pilot_20261011_v1")
OUTPUT = Path("reports/results/conference_validation_20261013_v1/instability")
PROTOCOL = Path("docs/conference_instability_protocol.md")
CORE_OFFSETS = ((0.0, 0.0),) + tuple(
    (dx, dy)
    for distance in (50.0, 100.0)
    for dx, dy in ((distance, 0.0), (-distance, 0.0), (0.0, distance), (0.0, -distance))
)
STRONG_OPTIONS = curved_front.QuadraticFrontFitOptions(
    maximum_function_evaluations=10_000,
    positive_curvature_seeds_ns=(1.0, 25.0, 100.0, 500.0, 2500.0),
    optimizer_ftol=1e-12,
    optimizer_xtol=1e-12,
    optimizer_gtol=1e-12,
)
FAILURES = (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError)


def json_safe(value):
    """Serialize diagnostics strictly, replacing nonfinite values with null."""
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


def write_json(path: Path, content: object) -> None:
    path.write_text(json.dumps(json_safe(content), indent=2, allow_nan=False) + "\n")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def select_cases(metrics: pd.DataFrame) -> pd.DataFrame:
    """Deterministic targeted selection; never use published-direction agreement."""
    required = {
        "event_id",
        "model",
        "weighting",
        "number_of_stations",
        "full_success",
        "heldout_complete",
        "maximum_loo_direction_shift_deg",
        "reduced_chi_square",
    }
    if not required <= set(metrics):
        raise ValueError("Baseline metrics lack required selection columns.")
    candidates = metrics.loc[
        (metrics.model == "quadratic")
        & (metrics.weighting == "timing")
        & metrics.full_success
        & metrics.heldout_complete
        & (metrics.number_of_stations >= 7)
    ].copy()
    if candidates.empty or candidates.event_id.duplicated().any():
        raise ValueError("Need nonempty unique complete quadratic timing cases.")
    if (
        not np.isfinite(candidates[["maximum_loo_direction_shift_deg", "reduced_chi_square"]])
        .all()
        .all()
    ):
        raise ValueError("Selection metrics must be finite.")
    candidates["event_id"] = candidates.event_id.astype(str).str.zfill(12)
    influence = candidates.sort_values(
        ["maximum_loo_direction_shift_deg", "event_id"], ascending=[False, True]
    ).head(3)
    high_chi = candidates.sort_values(
        ["reduced_chi_square", "event_id"], ascending=[False, True]
    ).head(2)
    roles: dict[str, list[str]] = {}
    for label, frame in (("top_influence", influence), ("high_chi_square", high_chi)):
        for identifier in frame.event_id:
            roles.setdefault(identifier, []).append(label)
    for count in sorted(influence.number_of_stations.unique()):
        matched = candidates[candidates.number_of_stations == count]
        stable = matched[matched.maximum_loo_direction_shift_deg < 1.0].copy()
        if stable.empty:
            chosen = matched.sort_values(["maximum_loo_direction_shift_deg", "event_id"]).iloc[0]
            role = "lowest_influence_fallback"
        else:
            median = stable.maximum_loo_direction_shift_deg.median()
            stable["median_distance"] = abs(stable.maximum_loo_direction_shift_deg - median)
            chosen = stable.sort_values(["median_distance", "event_id"]).iloc[0]
            role = "matched_stable_median"
        roles.setdefault(chosen.event_id, []).append(role)
    selected = candidates.set_index("event_id").loc[list(roles)].reset_index()
    selected["selection_roles"] = [";".join(roles[identifier]) for identifier in selected.event_id]
    return selected.sort_values("event_id").reset_index(drop=True)


def _finite(value: ArrayLike, name: str) -> FloatArray:
    original = np.asarray(value)
    if original.dtype.kind not in "iuf" or not np.isfinite(original).all():
        raise ValueError(f"{name} must contain finite real numbers.")
    return np.array(original, dtype=np.float64, copy=True)


def _data(positions, times, sigma, core):
    positions, times, sigma, core = (
        _finite(value, name)
        for value, name in (
            (positions, "positions"),
            (times, "times"),
            (sigma, "sigma"),
            (core, "core"),
        )
    )
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) < 3:
        raise ValueError("Need positions of shape (N,3), N >= 3.")
    if times.shape != (len(positions),) or sigma.shape != times.shape or core.shape != (3,):
        raise ValueError("Positions, times, uncertainties, and core must align.")
    if np.any(sigma <= 0):
        raise ValueError("Timing uncertainties must be positive.")
    return positions, times, sigma, core


def sky_from_slopes(slopes: ArrayLike) -> FloatArray:
    slopes = _finite(slopes, "slopes")
    if slopes.shape != (2,):
        raise ValueError("Need two sky slopes.")
    return np.append(slopes, 1.0) / np.hypot(np.hypot(*slopes), 1.0)


def profile_direction(positions, times, sigma, core, sky) -> dict:
    """Independent convex time/curvature solve at a fixed unit sky direction.

    Weighted centering gives the least-squares slope. If negative, the exact
    constrained optimum lies at A=0, with time refitted. No published direction
    is consumed. Epoch centering protects precision at large absolute times.
    """
    positions, times, sigma, core = _data(positions, times, sigma, core)
    sky = _finite(sky, "sky")
    if (
        sky.shape != (3,)
        or sky[2] <= 0
        or not np.isclose(np.linalg.norm(sky), 1, atol=1e-12, rtol=0)
    ):
        raise ValueError("Sky direction must be unit length and above the horizon.")
    displacement = positions - core
    along = displacement @ (-sky)
    # Cross-product form is deliberately independent of the production projection.
    rho2 = np.sum(np.cross(displacement, sky) ** 2, axis=1)
    x = rho2 / 1e6
    epoch = float(times[0])
    y = times - epoch - along / plane_front.C_M_PER_NS
    weights = (sigma.min() / sigma) ** 2
    weights /= weights.sum()
    xbar, ybar = float(weights @ x), float(weights @ y)
    xc = x - xbar
    denominator = float(weights @ xc**2)
    if denominator <= np.finfo(float).eps * max(1.0, float(weights @ x**2)):
        raise ValueError("Distances do not identify time and curvature separately.")
    delay = max(0.0, float(weights @ (xc * (y - ybar))) / denominator)
    intercept = ybar - delay * xbar
    residuals = y - intercept - delay * x
    standardized = residuals / sigma
    return {
        "sky_direction": sky,
        "time_origin_ns": epoch,
        "centered_core_time_ns": intercept,
        "delay_at_1km_ns": delay,
        "residuals_ns": residuals,
        "standardized_residuals": standardized,
        "objective_sum_squares": float(standardized @ standardized),
    }


def prediction_and_jacobian(parameters, positions, core):
    """Independent centered model and six-column analytic derivative.

    Parameter order is time, two sky slopes, A(ns/km^2), core-x and core-y(m).
    The final two columns diagnose local coupling only; core is not fitted.
    """
    p = _finite(parameters, "parameters")
    if p.shape != (6,):
        raise ValueError("Need six diagnostic parameters.")
    positions = _finite(positions, "positions")
    core = _finite(core, "core")
    if positions.ndim != 2 or positions.shape[1] != 3 or core.shape != (3,):
        raise ValueError("Need (N,3) station positions and a three-component core.")
    shifted_core = core + np.array([p[4], p[5], 0.0])
    displacement = positions - shifted_core
    norm = np.hypot(np.hypot(p[1], p[2]), 1.0)
    sky = np.array([p[1], p[2], 1.0]) / norm
    propagation = -sky
    along = displacement @ propagation
    rho2 = np.sum(np.cross(displacement, sky) ** 2, axis=1)
    derivative_sky = (np.eye(3)[:, :2] - sky[:, None] * sky[None, :2]) / norm
    derivative_along = -displacement @ derivative_sky
    curvature = p[3] / 1e6
    direction_columns = (1 / plane_front.C_M_PER_NS - 2 * curvature * along)[
        :, None
    ] * derivative_along
    transverse = displacement - along[:, None] * propagation
    core_columns = -propagation[:2] / plane_front.C_M_PER_NS - 2 * curvature * transverse[:, :2]
    jacobian = np.column_stack(
        (np.ones(len(positions)), direction_columns, rho2 / 1e6, core_columns)
    )
    predictions = p[0] + along / plane_front.C_M_PER_NS + curvature * rho2
    return predictions, jacobian


def jacobian_diagnostics(parameters, positions, core, sigma) -> dict:
    """Column-normalized singular spectrum and independent central-difference check."""
    parameters = np.asarray(parameters, dtype=float)
    _, jacobian = prediction_and_jacobian(parameters, positions, core)
    steps = np.array([0.01, 1e-5, 1e-5, 0.01, 0.01, 0.01])
    numerical = np.empty_like(jacobian)
    for column, step in enumerate(steps):
        delta = np.eye(6)[column] * step
        upper = prediction_and_jacobian(parameters + delta, positions, core)[0]
        lower = prediction_and_jacobian(parameters - delta, positions, core)[0]
        numerical[:, column] = (upper - lower) / (2 * step)
    error = float(np.max(abs(jacobian - numerical) / np.maximum(1.0, abs(jacobian))))
    result = {"central_difference_max_scaled_error": error}
    for count, name in ((4, "fixed_core"), (6, "augmented_core_xy")):
        weighted = jacobian[:, :count] / np.asarray(sigma)[:, None]
        norms = np.linalg.norm(weighted, axis=0)
        normalized = np.divide(weighted, norms, out=np.zeros_like(weighted), where=norms > 0)
        singular = np.linalg.svd(normalized, compute_uv=False)
        result[name + "_singular_values"] = singular
        result[name + "_rank"] = int(np.count_nonzero(singular > singular[0] * 1e-10))
        result[name + "_condition"] = (
            float(singular[0] / singular[-1]) if singular[-1] > 0 else float("inf")
        )
        if count == 4:
            orthogonal, _, _ = np.linalg.svd(normalized, full_matrices=False)
            leverage = np.sum(orthogonal**2, axis=1)
            result["fixed_core_local_leverage"] = leverage
    return result


def spherical_path(first, second, count: int = 101) -> FloatArray:
    """Shortest upper-hemisphere unit-vector arc, including both endpoints."""
    first, second = (_finite(v, "direction") for v in (first, second))
    if count < 2 or any(
        v.shape != (3,) or v[2] <= 0 or not np.isclose(np.linalg.norm(v), 1.0)
        for v in (first, second)
    ):
        raise ValueError("Need two upward unit vectors and at least two path points.")
    angle = np.arctan2(np.linalg.norm(np.cross(first, second)), np.dot(first, second))
    fraction = np.linspace(0, 1, count)
    if angle < 1e-10:
        path = (1 - fraction[:, None]) * first + fraction[:, None] * second
    else:
        path = (
            np.sin((1 - fraction) * angle)[:, None] * first
            + np.sin(fraction * angle)[:, None] * second
        ) / np.sin(angle)
    return path / np.linalg.norm(path, axis=1)[:, None]


def independent_multistart(positions, times, sigma, core, directions) -> list[dict]:
    """Solve the same objective by variable projection from fourteen directions."""
    positions, times, sigma, core = _data(positions, times, sigma, core)
    seeds = [
        (
            f"grid_{theta}_{phi}",
            plane_front.sky_direction_from_angles(np.deg2rad(theta), np.deg2rad(phi)),
        )
        for theta in (20, 50, 75)
        for phi in (0, 90, 180, 270)
    ]
    seeds += [(f"archived_{index}", np.asarray(sky)) for index, sky in enumerate(directions)]

    def residual(slopes):
        return profile_direction(positions, times, sigma, core, sky_from_slopes(slopes))[
            "standardized_residuals"
        ]

    outcomes = []
    for label, sky in seeds:
        record = {"initializer": label, "initial_sky": sky, "success": False}
        try:
            solved = least_squares(
                residual,
                sky[:2] / sky[2],
                jac="3-point",
                method="trf",
                x_scale="jac",
                ftol=1e-12,
                xtol=1e-12,
                gtol=1e-12,
                max_nfev=10_000,
            )
            result = profile_direction(positions, times, sigma, core, sky_from_slopes(solved.x))
            record.update(result)
            record.update(
                success=bool(solved.success),
                status=int(solved.status),
                message=str(solved.message),
                nfev=int(solved.nfev),
                njev=int(solved.njev),
                cost=float(solved.cost),
                optimality=float(solved.optimality),
                final_slopes=solved.x,
            )
        except FAILURES as error:
            record.update(exception_type=type(error).__name__, message=str(error))
        outcomes.append(record)
    return outcomes


def _fit_record(positions, times, sigma, core, options) -> dict:
    try:
        fit = curved_front.fit_quadratic_front(
            positions, times, sigma, core_position_m=core, options=options
        )
        return {"success": True, "result": fit}
    except FAILURES as error:
        return {
            "success": False,
            "exception_type": type(error).__name__,
            "message": str(error),
            "attempts": getattr(error, "attempts", ()),
        }


def _archived_payload(path: Path) -> dict:
    """Receipt envelope integrity check using the archived writer's canonical JSON."""
    envelope = json.loads(path.read_text())
    canonical = json.dumps(
        envelope["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if sha256(canonical).hexdigest() != envelope["sha256"]:
        raise RuntimeError(f"Archived receipt failed hash verification: {path}")
    return envelope["payload"]


def _sky(record: dict) -> FloatArray:
    return np.array([record["sky_x"], record["sky_y"], record["sky_z"]])


def _station_rows(document, inputs, archived, baseline_fit, omitted_id) -> pd.DataFrame:
    by_id = {int(station["id"]): station for station in document["stations"]}
    if len(by_id) != len(document["stations"]):
        raise ValueError("Duplicate station IDs in raw event.")
    records = {
        int(row["held_out_station_id"]): row
        for row in archived["records"]
        if row["stage"] == "leave_one_out"
        and row["model"] == "quadratic"
        and row["weighting"] == "timing"
        and row["success"]
    }
    parameters = np.array([*baseline_fit.optimizer_parameters, 0.0, 0.0])
    diagnostic = jacobian_diagnostics(
        parameters,
        inputs.station_positions_m,
        baseline_fit.core_position_m,
        inputs.timing_uncertainties_ns,
    )
    offsets = inputs.station_positions_m - baseline_fit.core_position_m
    radii = np.linalg.norm(np.cross(offsets, baseline_fit.sky_direction), axis=1)
    weight_fraction = inputs.timing_uncertainties_ns**-2
    weight_fraction /= weight_fraction.sum()
    rows = []
    for index, identifier in enumerate(inputs.station_ids):
        station = by_id[int(identifier)]
        rows.append(
            {
                "station_id": int(identifier),
                "x_m": inputs.station_positions_m[index, 0],
                "y_m": inputs.station_positions_m[index, 1],
                "z_m": inputs.station_positions_m[index, 2],
                "observed_time_ns": inputs.observed_times_ns[index],
                "dt_ns": inputs.timing_uncertainties_ns[index],
                "signal_vem": station.get("signal"),
                "dsignal_vem": station.get("dsignal"),
                "sat": station.get("sat"),
                "isSelected": station.get("isSelected"),
                "fitted_axis_distance_m": radii[index],
                "timing_weight_fraction": weight_fraction[index],
                "full_residual_ns": baseline_fit.residuals_ns[index],
                "full_standardized_residual": baseline_fit.standardized_residuals[index],
                "local_leverage": diagnostic["fixed_core_local_leverage"][index],
                "archived_loo_shift_deg": records[int(identifier)]["direction_shift_from_full_deg"],
                "worst_omitted_station": int(identifier) == omitted_id,
            }
        )
    return pd.DataFrame(rows)


def run_event(root: Path, selected: pd.Series, output: Path) -> dict:
    """Run every declared experiment for one verified, previously unblinded event."""
    identifier = selected.event_id
    destination = output / "events" / identifier
    destination.mkdir(parents=True, exist_ok=False)
    archived_path = root / BASELINE / "events" / identifier / "predictions.json"
    archived = _archived_payload(archived_path)
    raw_path = root / "data/raw/events" / f"Auger_{identifier}.json"
    if digest(raw_path) != archived["raw_sha256"]:
        raise RuntimeError("Selected raw event changed since the frozen baseline.")
    inputs = event_json.load_auger_plane_front_input(raw_path)
    core = core_reference.load_auger_core_reference(raw_path).position_m
    positions, times, sigma = (
        inputs.station_positions_m,
        inputs.observed_times_ns,
        inputs.timing_uncertainties_ns,
    )
    if not np.array_equal(positions, archived["inputs"]["positions_m"]) or not np.array_equal(
        core, archived["inputs"]["published_core_position_m"]
    ):
        raise RuntimeError("Adapted coordinates differ from archived inputs.")
    records = [
        row
        for row in archived["records"]
        if row["model"] == "quadratic" and row["weighting"] == "timing" and row["success"]
    ]
    full_archived = next(row for row in records if row["stage"] == "full")
    worst = sorted(
        (row for row in records if row["stage"] == "leave_one_out"),
        key=lambda row: (-row["direction_shift_from_full_deg"], int(row["held_out_station_id"])),
    )[0]
    omitted = int(worst["held_out_station_id"])
    masks = {
        "full": np.ones(len(times), dtype=bool),
        "worst_omission": inputs.station_ids != omitted,
    }
    write_json(
        destination / "input_provenance.json",
        {
            "event_id": identifier,
            "selection": selected.to_dict(),
            "raw_sha256": digest(raw_path),
            "archived_sha256": digest(archived_path),
            "omitted_station": omitted,
            "inputs": archived["inputs"],
            "full_archived": full_archived,
            "worst_archived": worst,
        },
    )
    shutil.copy2(archived_path, destination / "archived_predictions.json")
    rows, core_rows, profiles, raw_results, checks = [], [], [], {}, []
    full_fit = None
    path = spherical_path(_sky(full_archived), _sky(worst))
    for context, mask in masks.items():
        p, t, s = positions[mask], times[mask], sigma[mask]
        archived_record = full_archived if context == "full" else worst
        current = {}
        for settings, options in (("default", None), ("strong", STRONG_OPTIONS)):
            record = _fit_record(p, t, s, core, options)
            current[settings] = record
            row = {
                "event_id": identifier,
                "context": context,
                "solver": settings,
                "success": record["success"],
                "number_of_stations": len(t),
                "omitted_station_id": omitted if context != "full" else None,
            }
            if record["success"]:
                fit = record["result"]
                independent = profile_direction(p, t, s, core, fit.sky_direction)
                check = jacobian_diagnostics(
                    np.array([*fit.optimizer_parameters, 0, 0]), p, core, s
                )
                checks.append({"context": context, "settings": settings, **check})
                row.update(
                    objective=fit.objective_sum_squares,
                    archived_objective=archived_record["objective_sum_squares"],
                    reduced_chi_square=fit.reduced_chi_square,
                    delay_at_1km_ns=fit.delay_at_1km_ns,
                    shift_from_archived_deg=plane_front.angular_separation_deg(
                        fit.sky_direction, _sky(archived_record)
                    ),
                    shift_from_full_deg=plane_front.angular_separation_deg(
                        fit.sky_direction, _sky(full_archived)
                    ),
                    fixed_core_condition=check["fixed_core_condition"],
                    augmented_core_condition=check["augmented_core_xy_condition"],
                    independent_profile_objective=independent["objective_sum_squares"],
                    optimizer_optimality=fit.optimizer_optimality,
                )
                if context == "full" and settings == "default":
                    full_fit = fit
            else:
                row.update(failure_type=record["exception_type"], failure_message=record["message"])
            rows.append(row)
        attempts = independent_multistart(p, t, s, core, [_sky(full_archived), _sky(worst)])
        current["independent_profile_multistart"] = attempts
        for attempt in attempts:
            row = {
                "event_id": identifier,
                "context": context,
                "solver": "independent_profile",
                "initializer": attempt["initializer"],
                "success": attempt["success"],
                "number_of_stations": len(t),
            }
            if attempt["success"]:
                row.update(
                    objective=attempt["objective_sum_squares"],
                    archived_objective=archived_record["objective_sum_squares"],
                    delay_at_1km_ns=attempt["delay_at_1km_ns"],
                    shift_from_archived_deg=plane_front.angular_separation_deg(
                        attempt["sky_direction"], _sky(archived_record)
                    ),
                    shift_from_full_deg=plane_front.angular_separation_deg(
                        attempt["sky_direction"], _sky(full_archived)
                    ),
                    optimizer_optimality=attempt["optimality"],
                )
            else:
                row.update(
                    failure_type=attempt.get("exception_type", "OptimizerFailure"),
                    failure_message=attempt["message"],
                )
            rows.append(row)
        current["core_offset_results"] = []
        for dx, dy in CORE_OFFSETS:
            shifted = core + [dx, dy, 0]
            outcome = _fit_record(p, t, s, shifted, STRONG_OPTIONS)
            current["core_offset_results"].append({"dx_m": dx, "dy_m": dy, **outcome})
            row = {
                "event_id": identifier,
                "context": context,
                "dx_m": dx,
                "dy_m": dy,
                "success": outcome["success"],
            }
            if outcome["success"]:
                fit = outcome["result"]
                row.update(
                    objective=fit.objective_sum_squares,
                    reduced_chi_square=fit.reduced_chi_square,
                    delay_at_1km_ns=fit.delay_at_1km_ns,
                    sky_x=fit.sky_direction[0],
                    sky_y=fit.sky_direction[1],
                    sky_z=fit.sky_direction[2],
                    shift_from_archived_deg=plane_front.angular_separation_deg(
                        fit.sky_direction, _sky(archived_record)
                    ),
                )
            else:
                row.update(
                    failure_type=outcome["exception_type"], failure_message=outcome["message"]
                )
            core_rows.append(row)
        for fraction, sky in zip(np.linspace(0, 1, len(path)), path, strict=True):
            row = {
                "event_id": identifier,
                "context": context,
                "arc_fraction": fraction,
                "angle_from_full_deg": plane_front.angular_separation_deg(sky, _sky(full_archived)),
            }
            try:
                point = profile_direction(p, t, s, core, sky)
                row.update(
                    success=True,
                    objective=point["objective_sum_squares"],
                    delay_at_1km_ns=point["delay_at_1km_ns"],
                )
            except FAILURES as error:
                row.update(
                    success=False, failure_type=type(error).__name__, failure_message=str(error)
                )
            profiles.append(row)
        raw_results[context] = current
    if full_fit is None:
        raise RuntimeError(
            "Baseline could not be reproduced; preserve failure artifacts and investigate."
        )
    stations = _station_rows(json.loads(raw_path.read_text()), inputs, archived, full_fit, omitted)
    stations.to_csv(destination / "station_diagnostics.csv", index=False)
    pd.DataFrame(rows).to_csv(destination / "solver_comparison.csv", index=False)
    pd.DataFrame(core_rows).to_csv(destination / "core_sensitivity.csv", index=False)
    pd.DataFrame(profiles).to_csv(destination / "direction_profiles.csv", index=False)
    write_json(destination / "jacobian_checks.json", checks)
    write_json(destination / "all_fit_attempts.json", raw_results)
    write_json(
        destination / "receipt.json",
        {
            "event_id": identifier,
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "artifacts": {
                item.name: digest(item) for item in destination.iterdir() if item.is_file()
            },
        },
    )
    return {
        "event_id": identifier,
        "rows": rows,
        "core_rows": core_rows,
        "profiles": profiles,
        "checks": checks,
        "stations": stations,
    }


def make_figures(output: Path, cases: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for case in cases:
        identifier = case["event_id"]
        stations = case["stations"]
        profile = pd.DataFrame(case["profiles"])
        core = pd.DataFrame(case["core_rows"])
        fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout="constrained")
        scatter = axes[0, 0].scatter(
            stations.x_m,
            stations.y_m,
            c=stations.full_standardized_residual,
            s=40 + 600 * stations.timing_weight_fraction,
            cmap="coolwarm",
        )
        for _, station in stations.iterrows():
            axes[0, 0].annotate(
                str(int(station.station_id)),
                (station.x_m, station.y_m),
                xytext=(5, 5),
                textcoords="offset points",
            )
        axes[0, 0].set(
            xlabel="Site x (m)",
            ylabel="Site y (m)",
            title="Station geometry; marker area tracks timing weight",
        )
        axes[0, 0].set_aspect("equal", adjustable="datalim")
        fig.colorbar(scatter, ax=axes[0, 0], label="Full-fit standardized timing residual")
        for context, group in profile.groupby("context", sort=False):
            axes[0, 1].plot(
                group.angle_from_full_deg,
                group.objective - group.objective.min(),
                label=context.replace("_", " "),
            )
        axes[0, 1].set(
            xlabel="Angle along full-to-omitted direction arc (deg)",
            ylabel="Objective minus minimum on displayed path",
            title="Time and curvature profiled at each direction",
        )
        axes[0, 1].legend()
        axes[1, 0].bar(stations.station_id.astype(str), stations.archived_loo_shift_deg)
        axes[1, 0].set(
            xlabel="Omitted station ID",
            ylabel="Direction change (deg)",
            title="Conditional leave-one-out influence",
        )
        axes[1, 0].tick_params(axis="x", rotation=45)
        for context, group in core.groupby("context", sort=False):
            axes[1, 1].scatter(
                group.shift_from_archived_deg,
                group.reduced_chi_square,
                label=context.replace("_", " "),
            )
        axes[1, 1].set(
            xlabel="Direction change under core offset (deg)",
            ylabel="Nominal reduced chi-square",
            title="Fixed ±50/±100 m x/y sensitivity probes",
        )
        axes[1, 1].legend()
        fig.suptitle(f"Training event {identifier}: core-assisted quadratic timing diagnostics")
        for extension in ("png", "svg"):
            fig.savefig(output / "events" / identifier / f"diagnostics.{extension}", dpi=180)
        plt.close(fig)


def run(root: Path) -> None:
    root = root.resolve()
    output = root / OUTPUT
    if output.exists():
        raise FileExistsError("Diagnostic run already exists; do not overwrite a frozen study.")
    metric_path = root / BASELINE / "report/training_event_metrics.csv"
    columns = [
        "event_id",
        "model",
        "weighting",
        "number_of_stations",
        "full_success",
        "heldout_complete",
        "maximum_loo_direction_shift_deg",
        "reduced_chi_square",
    ]
    metrics = pd.read_csv(metric_path, usecols=columns, dtype={"event_id": str})
    selected = select_cases(metrics)
    manifest_path = root / "data/manifests/pilot_sd1500_vertical_v1.csv"
    # Read only identity/split, not protected reference-direction columns.
    manifest = pd.read_csv(manifest_path, usecols=["event_id", "split"], dtype=str)
    manifest["event_id"] = manifest.event_id.str.zfill(12)
    train_ids = set(manifest.loc[manifest.split == "train", "event_id"])
    if not set(selected.event_id) <= train_ids or "081881294400" not in set(selected.event_id):
        raise RuntimeError("Case selection violated frozen training/extreme-event contract.")
    source_paths = [
        Path(__file__).resolve(),
        Path(curved_front.__file__).resolve(),
        Path(plane_front.__file__).resolve(),
        Path(core_reference.__file__).resolve(),
        Path(event_json.__file__).resolve(),
        root / PROTOCOL,
        metric_path,
        manifest_path,
        root / BASELINE / "configuration.json",
    ]
    source_hashes = {str(path.relative_to(root)): digest(path) for path in source_paths}
    output.mkdir(parents=True, exist_ok=False)
    selected.to_csv(output / "selected_cases.csv", index=False)
    for source in source_paths:
        destination = output / "source_snapshot" / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    configuration = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "protocol": str(PROTOCOL),
        "source_hashes": source_hashes,
        "settings": asdict(STRONG_OPTIONS),
        "core_offsets_m": CORE_OFFSETS,
        "profile_points": 101,
        "independent_direction_grid": {"theta_deg": [20, 50, 75], "phi_deg": [0, 90, 180, 270]},
        "protected_event_access": False,
        "packages": {name: version(name) for name in ("numpy", "scipy", "pandas", "matplotlib")},
    }
    write_json(output / "configuration.json", configuration)
    print("Frozen cases:", selected[["event_id", "selection_roles"]].to_dict("records"), flush=True)
    cases = []
    for _, case in selected.iterrows():
        print("Starting", case.event_id, flush=True)
        result = run_event(root, case, output)
        cases.append(result)
        rows = pd.DataFrame(result["rows"])
        print(
            "Finished",
            case.event_id,
            rows.groupby(["context", "solver"]).objective.min().to_dict(),
            flush=True,
        )
    make_figures(output, cases)
    pd.DataFrame([row for case in cases for row in case["rows"]]).to_csv(
        output / "all_solver_comparisons.csv", index=False
    )
    pd.DataFrame([row for case in cases for row in case["core_rows"]]).to_csv(
        output / "all_core_sensitivities.csv", index=False
    )
    pd.concat([case["stations"].assign(event_id=case["event_id"]) for case in cases]).to_csv(
        output / "all_station_diagnostics.csv", index=False
    )
    for relative, expected in source_hashes.items():
        if digest(root / relative) != expected:
            raise RuntimeError(f"Source/input changed during run: {relative}")
    write_json(
        output / "completion.json",
        {
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "event_count": len(cases),
            "protected_event_access": False,
            "maximum_jacobian_check_error": max(
                check["central_difference_max_scaled_error"]
                for case in cases
                for check in case["checks"]
            ),
            "artifact_hashes": {
                str(path.relative_to(output)): digest(path)
                for path in sorted(output.rglob("*"))
                if path.is_file()
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    run(args.root)


if __name__ == "__main__":
    main()
