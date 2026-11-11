"""Paired plane/quadratic timing comparisons, without reference-direction inputs.

Leave-one-station-out predictions refit only the retained station measurements.
The fixed core and station selection are nevertheless reused: when supplied by
Auger, this is a conditional diagnostic, not independent end-to-end validation.
Held-out residuals divided by measurement sigma are *not* predictive pulls:
parameter, core, and model uncertainty have not been propagated into that sigma.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from auger_reco.physics.curved_front import (
    QuadraticFrontFitOptions,
    QuadraticFrontFitResult,
    QuadraticFrontGeometryError,
    QuadraticFrontOptimizationError,
    fit_quadratic_front,
)
from auger_reco.physics.plane_front import (
    DegenerateStationGeometryError,
    PlaneFrontFitOptions,
    PlaneFrontFitResult,
    PlaneFrontInitializationError,
    PlaneFrontOptimizationError,
    WeightingMode,
    angular_separation_deg,
    fit_plane_front,
    predict_station_times_ns,
)
from auger_reco.physics.quadratic_front import quadratic_front_times_ns

type FrontModel = Literal["plane", "quadratic"]
type FrontFit = PlaneFrontFitResult | QuadraticFrontFitResult
type FloatArray = NDArray[np.float64]
type Record = dict[str, object]

_KNOWN_FIT_ERRORS = (
    DegenerateStationGeometryError,
    PlaneFrontInitializationError,
    PlaneFrontOptimizationError,
    QuadraticFrontGeometryError,
    QuadraticFrontOptimizationError,
)
_WEIGHTINGS: tuple[WeightingMode, ...] = ("timing", "uniform")
_MODELS: tuple[FrontModel, ...] = ("plane", "quadratic")


@dataclass(frozen=True, slots=True)
class FrontComparisonResult:
    """Exportable records plus successful full-data fit objects.

    Failure rows are retained with ``None`` metrics, never numerical zeros.
    Optimizer attempts retain their complete per-seed diagnostics. Arrays in
    fitter results retain the fitters' read-only guarantees; export rows are
    ordinary mutable dictionaries for downstream serialization.
    """

    records: list[Record]
    optimizer_attempts: list[Record]
    station_residuals: list[Record]
    full_fits: dict[tuple[FrontModel, WeightingMode], FrontFit]
    configuration: Record


def _finite_array(value: ArrayLike, name: str) -> FloatArray:
    """Validate real data before float conversion, without changing the caller."""
    try:
        original = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric data.") from error
    if original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numeric, non-Boolean data.")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.array(original, dtype=np.float64, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite float64 data.")
    return result


def predict_fit_times_ns(fit: FrontFit, positions_m: ArrayLike) -> FloatArray:
    """Predict at new stations with this fit's own reference and direction.

    The quadratic distance is recalculated from the fitted propagation vector,
    not an official reference direction or distances cached by the input file.
    """
    if isinstance(fit, PlaneFrontFitResult):
        return predict_station_times_ns(
            fit.reference_time_ns,
            fit.propagation_direction,
            positions_m,
            fit.reference_position_m,
        )
    if isinstance(fit, QuadraticFrontFitResult):
        return quadratic_front_times_ns(
            positions_m,
            fit.propagation_direction,
            fit.core_position_m,
            fit.core_time_ns,
            fit.curvature_ns_per_m2,
        )
    raise TypeError("fit must be a plane or quadratic front result.")


def _empty_metrics() -> Record:
    """Use a stable table schema even if every attempted fit fails."""
    return dict.fromkeys(
        (
            "nominal_degrees_of_freedom",
            "zenith_deg",
            "azimuth_deg",
            "sky_x",
            "sky_y",
            "sky_z",
            "delay_at_1km_ns",
            "chi_square",
            "reduced_chi_square",
            "rms_residual_ns",
            "maximum_absolute_residual_ns",
            "objective_sum_squares",
            "direction_shift_from_full_deg",
            "separation_from_plane_deg",
            "nested_objective_violation",
            "nested_objective_excess",
        )
    )


def compare_event_fronts(
    positions_m: ArrayLike,
    times_ns: ArrayLike,
    uncertainties_ns: ArrayLike,
    core_position_m: ArrayLike,
    *,
    station_ids: Sequence[str | int],
    plane_options: PlaneFrontFitOptions | None = None,
    curved_options: QuadraticFrontFitOptions | None = None,
    core_offsets_m: ArrayLike | None = None,
    run_leave_one_out: bool = True,
) -> FrontComparisonResult:
    """Fit full data, held-out stations, and fixed-core sensitivity cases.

    Both ``timing`` and ``uniform`` weightings are used for full and leave-one-out
    fits. Core-shift fits use the quadratic model and timing weighting only.
    Default offsets are +/-100 m independently along x and y; an empty (0, 3)
    array disables these cases. They are sensitivity scenarios, not probability
    distributions or confidence intervals. Core uncertainty is never refitted.

    Inputs must be finite real arrays, with positive timing uncertainties and
    unique station identifiers. Geometry/initializer/optimizer failures are
    recorded and remaining fits continue. Programming errors and unexpected
    exceptions deliberately propagate instead of silently dropping a case.
    Folds with too few retained stations are explicitly recorded as failures.

    No published direction enters this function. Direction comparisons here
    concern our fits; comparison to an official direction belongs downstream.
    Nominal reduced chi-square does not account for the curvature boundary or
    shared-data core estimates. Uniform fits do not minimize physical chi-square.
    """
    plane_settings = plane_options if plane_options is not None else PlaneFrontFitOptions()
    curved_settings = curved_options if curved_options is not None else QuadraticFrontFitOptions()
    if not isinstance(plane_settings, PlaneFrontFitOptions):
        raise TypeError("plane_options must be PlaneFrontFitOptions or None.")
    if not isinstance(curved_settings, QuadraticFrontFitOptions):
        raise TypeError("curved_options must be QuadraticFrontFitOptions or None.")
    if plane_settings.optimizer_loss != "linear":
        raise ValueError("The paired nested-model comparison requires linear least-squares loss.")
    if not isinstance(run_leave_one_out, bool):
        raise TypeError("run_leave_one_out must be Boolean.")
    positions = _finite_array(positions_m, "positions_m")
    times = _finite_array(times_ns, "times_ns")
    sigmas = _finite_array(uncertainties_ns, "uncertainties_ns")
    core = _finite_array(core_position_m, "core_position_m")
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("positions_m must have shape (N, 3).")
    count = positions.shape[0]
    minimum = max(plane_settings.minimum_stations, curved_settings.minimum_stations)
    if count < minimum:
        raise ValueError(f"At least {minimum} stations are required for both full fits.")
    if times.shape != (count,) or sigmas.shape != (count,):
        raise ValueError("times_ns and uncertainties_ns must have shape (N,).")
    if np.any(sigmas <= 0.0) or core.shape != (3,):
        raise ValueError("Uncertainties must be positive and core_position_m must have shape (3,).")
    if isinstance(station_ids, (str, bytes)):
        raise ValueError("station_ids must be a sequence, not a string.")
    identifiers = list(station_ids)
    if len(identifiers) != count or any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (str, int, np.integer))
        or str(value).strip() == ""
        for value in identifiers
    ):
        raise ValueError("station_ids must supply one nonempty string or integer per station.")
    identifiers = [str(value) for value in identifiers]
    if len(set(identifiers)) != count:
        raise ValueError("station_ids must be unique after conversion to strings.")
    offsets = _finite_array(
        [[100.0, 0.0, 0.0], [-100.0, 0.0, 0.0], [0.0, 100.0, 0.0], [0.0, -100.0, 0.0]]
        if core_offsets_m is None
        else core_offsets_m,
        "core_offsets_m",
    )
    if offsets.ndim != 2 or offsets.shape[1] != 3:
        raise ValueError("core_offsets_m must have shape (K, 3), including (0, 3) to disable.")
    with np.errstate(over="ignore", invalid="ignore"):
        finite_geometry = np.isfinite(positions - core).all() and np.isfinite(core + offsets).all()
    if not finite_geometry:
        raise ValueError("Core offsets or station-core differences overflow float64.")

    records: list[Record] = []
    attempts: list[Record] = []
    station_records: list[Record] = []
    full_fits: dict[tuple[FrontModel, WeightingMode], FrontFit] = {}

    def run_fit(
        model: FrontModel,
        weighting: WeightingMode,
        stage: str,
        scenario: str,
        selected: NDArray[np.int64],
        offset: FloatArray,
        held_out: int | None = None,
    ) -> None:
        """Execute one predeclared comparison and retain successes and failures."""
        context: Record = {
            "fit_id": f"{stage}/{scenario}/{model}/{weighting}",
            "stage": stage,
            "scenario": scenario,
            "model": model,
            "weighting": weighting,
            "held_out_station_id": None if held_out is None else identifiers[held_out],
            "held_out_station_index": held_out,
            "core_offset_x_m": float(offset[0]),
            "core_offset_y_m": float(offset[1]),
            "core_offset_z_m": float(offset[2]),
        }
        row = {
            **context,
            **_empty_metrics(),
            "success": False,
            "failure_type": None,
            "failure_message": None,
            "number_of_stations": len(selected),
            "quality_flags": (),
            "initializer_rejections": (),
            "initialization_messages": (),
        }
        required = (
            plane_settings.minimum_stations
            if model == "plane"
            else curved_settings.minimum_stations
        )
        if len(selected) < required:
            row.update(
                failure_type="InsufficientStations",
                failure_message=f"{len(selected)} retained stations; {required} required.",
            )
            records.append(row)
            return
        try:
            if model == "plane":
                fit = fit_plane_front(
                    positions[selected],
                    times[selected],
                    sigmas[selected],
                    weighting=weighting,
                    options=plane_settings,
                )
            else:
                fit = fit_quadratic_front(
                    positions[selected],
                    times[selected],
                    sigmas[selected],
                    core_position_m=core + offset,
                    weighting=weighting,
                    options=curved_settings,
                )
        except _KNOWN_FIT_ERRORS as error:
            row.update(
                failure_type=type(error).__name__,
                failure_message=str(error),
                initializer_rejections=getattr(error, "rejected_initializers", ()),
            )
            for attempt in getattr(error, "attempts", ()):
                attempts.append({**context, **asdict(attempt)})
            records.append(row)
            return
        row.update(
            success=True,
            nominal_degrees_of_freedom=fit.degrees_of_freedom,
            zenith_deg=fit.zenith_deg,
            azimuth_deg=fit.azimuth_deg,
            sky_x=float(fit.sky_direction[0]),
            sky_y=float(fit.sky_direction[1]),
            sky_z=float(fit.sky_direction[2]),
            delay_at_1km_ns=fit.delay_at_1km_ns if model == "quadratic" else 0.0,
            chi_square=fit.chi_square,
            reduced_chi_square=fit.reduced_chi_square,
            rms_residual_ns=fit.rms_residual_ns,
            maximum_absolute_residual_ns=fit.maximum_absolute_residual_ns,
            objective_sum_squares=fit.objective_sum_squares,
            quality_flags=fit.quality_flags,
            initializer_rejections=getattr(fit, "initializer_rejections", ()),
            initialization_messages=getattr(fit, "initialization_messages", ()),
        )
        for attempt in fit.optimizer_attempts:
            attempts.append({**context, **asdict(attempt)})
        if stage == "full":
            full_fits[model, weighting] = fit
        baseline = full_fits.get((model, weighting))
        if baseline is not None:
            row["direction_shift_from_full_deg"] = angular_separation_deg(
                fit.sky_direction, baseline.sky_direction
            )
        records.append(row)
        # Full data: every residual. Leave-one-out: only the omitted prediction.
        # Core shifts retain fit metrics; full residual tables already cover baseline.
        evaluation_indices = (
            selected
            if stage == "full"
            else (
                np.array([held_out], dtype=np.int64)
                if held_out is not None
                else np.array([], dtype=int)
            )
        )
        if evaluation_indices.size:
            predicted = predict_fit_times_ns(fit, positions[evaluation_indices])
            distances = np.linalg.norm(
                np.cross(
                    positions[evaluation_indices] - (core + offset), fit.propagation_direction
                ),
                axis=1,
            )
            for index, prediction, distance in zip(
                evaluation_indices, predicted, distances, strict=True
            ):
                residual = float(times[index] - prediction)
                station_records.append(
                    {
                        **context,
                        "station_id": identifiers[index],
                        "station_index": int(index),
                        "observed_time_ns": float(times[index]),
                        "predicted_time_ns": float(prediction),
                        "residual_ns": residual,
                        "timing_uncertainty_ns": float(sigmas[index]),
                        "residual_over_observed_sigma": residual / float(sigmas[index]),
                        "axis_distance_m": float(distance),
                        "residual_kind": "in_sample" if stage == "full" else "held_out",
                    }
                )

    indices = np.arange(count, dtype=np.int64)
    zero = np.zeros(3, dtype=np.float64)
    for weighting in _WEIGHTINGS:
        for model in _MODELS:
            run_fit(model, weighting, "full", "baseline", indices, zero)
        plane = full_fits.get(("plane", weighting))
        curved = full_fits.get(("quadratic", weighting))
        if plane is not None and curved is not None:
            separation = angular_separation_deg(plane.sky_direction, curved.sky_direction)
            excess = curved.objective_sum_squares - plane.objective_sum_squares
            threshold = curved_settings.nested_objective_absolute_tolerance + (
                curved_settings.nested_objective_relative_tolerance * plane.objective_sum_squares
            )
            for row in records:
                if row["stage"] == "full" and row["weighting"] == weighting:
                    row["separation_from_plane_deg"] = (
                        separation if row["model"] == "quadratic" else 0.0
                    )
                    if row["model"] == "quadratic":
                        row["nested_objective_excess"] = excess
                        row["nested_objective_violation"] = bool(excess > threshold)
    if run_leave_one_out:
        for held_out in range(count):
            retained = indices[indices != held_out]
            for weighting in _WEIGHTINGS:
                for model in _MODELS:
                    run_fit(
                        model,
                        weighting,
                        "leave_one_out",
                        f"omit_{held_out}",
                        retained,
                        zero,
                        held_out,
                    )
    for index, offset in enumerate(offsets):
        run_fit("quadratic", "timing", "core_shift", f"core_shift_{index}", indices, offset)
    return FrontComparisonResult(
        records=records,
        optimizer_attempts=attempts,
        station_residuals=station_records,
        full_fits=full_fits,
        configuration={
            "plane_options": asdict(plane_settings),
            "curved_options": asdict(curved_settings),
            "station_ids": identifiers,
            "core_position_m": core.tolist(),
            "core_offsets_m": offsets.tolist(),
            "run_leave_one_out": run_leave_one_out,
            "core_shift_weighting": "timing",
            "core_shift_model": "quadratic",
            "leave_one_out_interpretation": (
                "Conditional on fixed core and station selection; not independent end-to-end CV."
            ),
            "residual_normalization": (
                "Observed measurement sigma only; not predictive uncertainty or a predictive pull."
            ),
            "reference_direction_used": False,
        },
    )
