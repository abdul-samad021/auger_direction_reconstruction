"""
Strict adapters from Pierre Auger event JSON to reconstruction inputs.
Validation is strict for every field consumed by the reconstruction, while
ignored measurements on excluded stations are deliberately left to a separate
whole-file integrity checker. The baseline adapter returns only detector-level
measurements and safe provenance metadata. Official reconstructed quantities
under ``sdrec`` are exposed through a separate reference loader so they cannot
accidentally enter the physics fit before a prediction has been frozen.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray

# Reusable type annotations for the NumPy arrays returned by this adapter.
type FloatArray = NDArray[np.float64]
type IntegerArray = NDArray[np.int64]

# Four stations give our three-parameter constrained fit at least one residual
# degree of freedom.
DEFAULT_MINIMUM_STATIONS = 4

# We have inspected and tested Auger's event JSON format version 2.
SUPPORTED_FORMAT_VERSIONS = frozenset({2})

# Station IDs will later be stored in an np.int64 array.
# These limits let us reject impossible values with a clear schema error before
# NumPy conversion.
INT64_MIN = int(np.iinfo(np.int64).min)
INT64_MAX = int(np.iinfo(np.int64).max)

# Released Auger event identifiers use a twelve-digit canonical representation.
MAX_CANONICAL_EVENT_ID = 999_999_999_999


class StationSelection(StrEnum):
    """Supported policies for choosing detector stations from one event."""

    OFFICIAL_SELECTED = "auger_isSelected"
    ALL_TRIGGERED = "all_triggered"


class DetectorArray(StrEnum):
    """Surface-detector array classification derived from released flags."""

    SD_1500 = "SD-1500"
    SD_750 = "SD-750"
    MIXED = "mixed"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True, slots=True)
class EventDataIssue:
    """One stable, machine-readable problem found in an event document."""

    code: str
    location: str
    message: str


class AugerEventDataError(ValueError):
    """Base exception for invalid Pierre Auger event data."""


class AugerEventDecodeError(AugerEventDataError):
    """Raised when a file cannot be decoded as JSON text."""

    def __init__(
        self, source_path: Path, message: str, *, line: int | None = None, column: int | None = None
    ) -> None:
        # Save structured information for tests, logs, and the future web API.
        self.source_path = source_path
        self.line = line
        self.column = column

        # Include the location only when both values are available.
        location = (
            f" at line {line}, column {column}" if line is not None and column is not None else ""
        )

        # Initialize the inherited ValueError message.
        super().__init__(f"Could not decode Auger event JSON {source_path}{location}: {message}")


class AugerEventSchemaError(AugerEventDataError):
    """Raised when decoded JSON violates the fitter-ready event contract."""

    def __init__(
        self, issues: tuple[EventDataIssue, ...], *, source_path: Path | None = None
    ) -> None:
        # An exception with no issues would be a programming error in this adapter.

        if not issues:
            raise ValueError("AugerEventSchemaError requires at least one issue.")

        self.issues = issues
        self.source_path = source_path

        # Use a readable fallback when adapting an in-memory dictionary.
        source = str(source_path) if source_path is not None else "in-memory event"

        # Convert every structured issue into one readable piece of text.
        details = "; ".join(
            f"{issue.code} at {issue.location}: {issue.message}" for issue in issues
        )

        super().__init__(f"Invalid Auger event data in {source}: {details}")


class AugerStationSelectionError(AugerEventDataError):
    """Raised when a station policy yields too few measurements for fitting."""

    def __init__(
        self,
        *,
        selection_policy: StationSelection,
        available_stations: int,
        required_stations: int,
        source_path: Path | None = None,
    ) -> None:
        self.selection_policy = selection_policy
        self.available_stations = available_stations
        self.required_stations = required_stations
        self.source_path = source_path

        source = str(source_path) if source_path is not None else "in-memory event"

        super().__init__(
            f"Station policy {selection_policy.value!r} selected "
            f"{available_stations} stations from {source}; at least "
            f"{required_stations} are required."
        )


@dataclass(frozen=True, slots=True)
class AugerPlaneFrontInput:
    """
    Immutable, leakage-controlled station measurements for one plane fit.
    Arrays preserve the released station order and use the units expected by
    :func:`auger_reco.physics.plane_front.fit_plane_front`: metres and
    nanoseconds. The object never contains Auger's official direction, core,
    energy, curvature, fit quality, or reconstructed station distances. Only
    the three numerical measurement arrays should enter the baseline fit or a
    future feature pipeline unless another field receives an explicit review.
    """

    # Event identity and data provenance.
    event_id: int
    canonical_event_id: str
    embedded_release: str
    format_version: int
    event_date: str | None
    source_path: Path | None

    # Detector and station-selection provenance
    detector_array: DetectorArray
    selection_policy: StationSelection
    triggered_station_count: int
    official_selected_station_count: int

    # Aligned station information. Index i refers to the same station everywhere.
    station_ids: IntegerArray
    station_names: tuple[str, ...]
    station_positions_m: FloatArray
    observed_times_ns: FloatArray
    timing_uncertainties_ns: FloatArray

    # Nonfatal conditions worth recording with the reconstruction.
    quality_flags: tuple[str, ...]

    @property
    def number_of_stations(self) -> int:
        """Number of aligned station rows returned under the chosen policy."""

        return len(self.station_ids)


@dataclass(frozen=True, slots=True)
class AugerDirectionReference:
    """
    Official direction target, intentionally separate from baseline inputs.
    ``embedded_release`` is the value stored inside the JSON document. It is
    not the public portal's release number; the two version labels need not
    match. ``format_version`` records the schema whose angle semantics were
    validated by this adapter.
    """

    # Identity fields let us match this reference to a frozen reconstruction.
    event_id: int
    canonical_event_id: str
    embedded_release: str
    format_version: int
    source_path: Path | None

    # Auger's official reconstructed sky-arrival direction.
    zenith_deg: float
    azimuth_deg: float

    # Some Auger event categories may omit one or both angle uncertainties.
    zenith_uncertainty_deg: float | None
    azimuth_uncertainty_deg: float | None


# A unique marker for absent keys; JSON null is represented by None instead.
_MISSING = object()


def _child_location(parent: str, field: str | int) -> str:
    """Build a location from our fixed schema keys or station indices."""

    if parent == "/":
        return f"/{field}"

    return f"{parent}/{field}"


def _record_issue(issues: list[EventDataIssue], *, code: str, location: str, message: str) -> None:
    """Add one structured issue to the caller's error list."""

    issues.append(EventDataIssue(code=code, location=location, message=message))


def _required_field(
    mapping: Mapping[str, object], field: str, *, parent_location: str, issues: list[EventDataIssue]
) -> object:
    """Read one required key and report its absence once."""

    try:
        return mapping[field]
    except KeyError:
        _record_issue(
            issues,
            code="missing_field",
            location=_child_location(parent_location, field),
            message=f"Required field {field!r} is absent.",
        )
        return _MISSING


def _optional_field(mapping: Mapping[str, object], field: str) -> object:
    """Read an optional key while preserving missing versus explicit null."""

    try:
        return mapping[field]
    except KeyError:
        return _MISSING


def _mapping_value(
    value: object, *, location: str, issues: list[EventDataIssue]
) -> Mapping[str, object] | None:
    """Validate an object without copying or inspecting all its fields."""

    if value is _MISSING:
        return None  # Its absence was already recorded by _required_field.

    if not isinstance(value, Mapping):
        _record_issue(
            issues, code="wrong_type", location=location, message="Expected a JSON object."
        )
        return None

    return value


def _non_empty_list_value(
    value: object, *, location: str, issues: list[EventDataIssue]
) -> list[object] | None:
    """Require a non-empty JSON array."""

    if value is _MISSING:
        return None

    if not isinstance(value, list):
        _record_issue(
            issues, code="wrong_type", location=location, message="Expected a JSON array."
        )
        return None

    if not value:
        _record_issue(
            issues,
            code="empty_value",
            location=location,
            message="The array must contain at least one item.",
        )
        return None

    return value


def _integer_value(
    value: object,
    *,
    location: str,
    issues: list[EventDataIssue],
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    """Require a built-in JSON integer within optional inclusive bounds."""

    if value is _MISSING:
        return None

    if type(value) is not int:  # Reject bool, float, and numeric strings.
        _record_issue(
            issues, code="wrong_type", location=location, message="Expected a JSON integer."
        )
        return None

    if minimum is not None and value < minimum:
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message=f"Integer must be at least {minimum}.",
        )
        return None

    if maximum is not None and value > maximum:
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message=f"Integer must be at most {maximum}.",
        )
        return None

    return value


def _finite_float_value(
    value: object,
    *,
    location: str,
    issues: list[EventDataIssue],
    minimum: float | None = None,
    maximum: float | None = None,
    strictly_positive: bool = False,
) -> float | None:
    """Validate a JSON number before converting it into a fitter value."""

    if value is _MISSING:
        return None

    if type(value) not in (int, float):  # JSON booleans are not measurements.
        _record_issue(
            issues, code="wrong_type", location=location, message="Expected a JSON number."
        )
        return None

    try:
        number = float(value)
    except OverflowError:
        # Do not print a potentially enormous invalid integer in the message.
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message="Number is too large to convert to a float64 value.",
        )
        return None

    if not np.isfinite(number):
        _record_issue(
            issues,
            code="nonfinite_number",
            location=location,
            message="Number must not be NaN or infinite.",
        )
        return None

    if strictly_positive and number <= 0.0:
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message="Number must be strictly positive.",
        )
        return None

    if minimum is not None and number < minimum:
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message=f"Number must be at least {minimum}.",
        )
        return None

    if maximum is not None and number > maximum:
        _record_issue(
            issues,
            code="out_of_range",
            location=location,
            message=f"Number must be at most {maximum}.",
        )
        return None

    return number


def _binary_flag_value(value: object, *, location: str, issues: list[EventDataIssue]) -> int | None:
    """Accept only the integer 0 or 1."""

    if value is _MISSING:
        return None

    if type(value) is not int or value not in (0, 1):
        _record_issue(
            issues,
            code="invalid_binary_flag",
            location=location,
            message="Expected the integer 0 or 1.",
        )
        return None

    return value


def _nonblank_string_value(
    value: object, *, location: str, issues: list[EventDataIssue]
) -> str | None:
    """Require meaningful text while preserving the released string."""

    if value is _MISSING:
        return None

    if not isinstance(value, str) or not value.strip():
        _record_issue(
            issues, code="wrong_type", location=location, message="Expected a nonblank string."
        )
        return None

    return value  # Validation does not silently trim source text.


def _readonly_float_array(values: ArrayLike) -> FloatArray:
    """Copy already-validated measurements into a contiguous read-only array."""

    result = np.array(values, dtype=np.float64, order="C", copy=True)
    result.setflags(write=False)  # Prevent ordinary accidental assignment.
    return result


def _readonly_integer_array(values: ArrayLike) -> IntegerArray:
    """Copy already-range-checked IDs into a contiguous read-only array."""

    result = np.array(values, dtype=np.int64, order="C", copy=True)
    result.setflags(write=False)
    return result


def _normalize_selection(selection: StationSelection | str) -> StationSelection:
    """Convert a supported selection value into its enum member."""

    try:
        return StationSelection(selection)
    except (TypeError, ValueError):
        allowed_values = ", ".join(repr(option.value) for option in StationSelection)
        raise ValueError(f"selection must be one of: {allowed_values}") from None


def _validate_minimum_stations(minimum_stations: int) -> int:
    """Reject invalid caller configuration before reading event data."""

    if type(minimum_stations) is not int:
        raise TypeError("minimum_stations must be an integer")

    if minimum_stations < DEFAULT_MINIMUM_STATIONS:
        raise ValueError(f"minimum_stations must be at least {DEFAULT_MINIMUM_STATIONS}")

    return minimum_stations


def _raise_schema_errors(issues: list[EventDataIssue], *, source_path: Path | None) -> None:
    """Raise once after the caller has checked all relevant fields."""

    if issues:
        raise AugerEventSchemaError(tuple(issues), source_path=source_path)


def _read_event_identity(
    document: Mapping[str, object], *, issues: list[EventDataIssue], include_date: bool = True
) -> tuple[int | None, str | None]:
    """Read event identity, optionally retaining unparsed date text.

    Missing dates are allowed. When consumed, a present date must be a
    nonblank string; explicit null is not treated as an absent field.
    The reference adapter can set include_date=False to avoid reading a
    field that its output does not use.
    """

    info = _mapping_value(
        _required_field(document, "info", parent_location="/", issues=issues),
        location="/info",
        issues=issues,
    )

    if info is None:
        return None, None  # Do not fabricate missing children of an invalid parent.

    event_id = _integer_value(
        _required_field(info, "id", parent_location="/info", issues=issues),
        location="/info/id",
        issues=issues,
        minimum=0,
        maximum=MAX_CANONICAL_EVENT_ID,
    )

    event_date: str | None = None

    if include_date:
        raw_date = _optional_field(info, "date")
        if raw_date is not _MISSING:
            event_date = _nonblank_string_value(raw_date, location="/info/date", issues=issues)

    return event_id, event_date


def _read_format_metadata(
    document: Mapping[str, object], *, issues: list[EventDataIssue]
) -> tuple[str | None, int | None]:
    """Read the embedded release identifier and supported JSON format.

    This adapter accepts nonnegative integer release identifiers and
    stores them as text. The embedded identifier is not the portal DOI
    or its release date. Invalid fields are reported through issues.
    """

    meta = _mapping_value(
        _required_field(document, "meta", parent_location="/", issues=issues),
        location="/meta",
        issues=issues,
    )

    if meta is None:
        return None, None

    release_id = _integer_value(
        _required_field(meta, "release", parent_location="/meta", issues=issues),
        location="/meta/release",
        issues=issues,
        minimum=0,
    )

    format_version = _integer_value(
        _required_field(meta, "format", parent_location="/meta", issues=issues),
        location="/meta/format",
        issues=issues,
        minimum=0,
    )

    if format_version is not None and format_version not in SUPPORTED_FORMAT_VERSIONS:
        _record_issue(
            issues,
            code="unsupported_format_version",
            location="/meta/format",
            message=f"Supported JSON format versions: {sorted(SUPPORTED_FORMAT_VERSIONS)}.",
        )
        format_version = None

    embedded_release: str | None = None
    if release_id is not None:
        try:
            embedded_release = str(release_id)
        except ValueError:
            # Python limits conversion of extraordinarily large integers to text.
            _record_issue(
                issues,
                code="out_of_range",
                location="/meta/release",
                message="Release identifier is too large to represent as a decimal text.",
            )

    return embedded_release, format_version


def _classify_detector_array(
    document: Mapping[str, object], *, issues: list[EventDataIssue]
) -> tuple[DetectorArray | None, tuple[str, ...]]:
    """Classify released detector flags without consulting reconstruction outputs.

    Invalid or missing flags add schema issues. Valid mixed or unclassified
    combinations instead return nonfatal quality flags; cohort filtering is
    a separate decision.
    """

    flags = _mapping_value(
        _required_field(document, "flags", parent_location="/", issues=issues),
        location="/flags",
        issues=issues,
    )

    if flags is None:
        return None, ()

    sd1500 = _binary_flag_value(
        _required_field(flags, "sd1500", parent_location="/flags", issues=issues),
        location="/flags/sd1500",
        issues=issues,
    )

    sd750 = _binary_flag_value(
        _required_field(flags, "sd750", parent_location="/flags", issues=issues),
        location="/flags/sd750",
        issues=issues,
    )

    if sd1500 is None or sd750 is None:
        return None, ()  # Malformed flags are not an unclassified detector array.

    if sd1500 == 1 and sd750 == 1:
        return DetectorArray.MIXED, ("mixed_surface_detector_flags",)
    if sd1500 == 1:
        return DetectorArray.SD_1500, ()
    if sd750 == 1:
        return DetectorArray.SD_750, ()

    return DetectorArray.UNCLASSIFIED, ("unclassified_surface_detector_array",)


def _read_station_measurements(
    station: Mapping[str, object],
    *,
    location: str,
    issues: list[EventDataIssue],
) -> tuple[tuple[float, float, float], float, float] | None:
    """Validate one included station's position, start time, and uncertainty."""

    values: dict[str, float] = {}
    fields = ("x", "y", "z", "t", "dt")

    for field in fields:
        value = _finite_float_value(
            _required_field(station, field, parent_location=location, issues=issues),
            location=_child_location(location, field),
            issues=issues,
            strictly_positive=(field == "dt"),
        )

        if value is not None:  # Zero coordinates and zero times are valid.
            values[field] = value

    if len(values) != len(fields):
        return None  # Keep all recorded issues; do not invent missing measurements.

    position_m = (values["x"], values["y"], values["z"])

    return position_m, values["t"], values["dt"]


def adapt_auger_plane_front_input(
    document: object,
    *,
    selection: StationSelection | str = StationSelection.OFFICIAL_SELECTED,
    minimum_stations: int = DEFAULT_MINIMUM_STATIONS,
    source_path: str | Path | None = None,
) -> AugerPlaneFrontInput:
    """Adapt decoded event JSON into aligned, leakage-controlled fit inputs.

    Validate each station's mapping, ID, and selection flag, including
    excluded stations. Validate names and measurements only for included
    stations. Malformed included rows invalidate the event; they are not
    silently dropped from a successful result.

    The default policy relies on Auger's released isSelected flag, which
    remains an explicit dependency on the official reconstruction.

    source_path labels provenance only; this function does not load a file.
    It never reads sdrec, fdrec, or reconstructed station distances.
    """

    policy = _normalize_selection(selection)
    required_count = _validate_minimum_stations(minimum_stations)
    resolved_source = None if source_path is None else Path(source_path).expanduser().resolve()

    if not isinstance(document, Mapping):
        raise AugerEventSchemaError(
            (EventDataIssue("wrong_type", "/", "Expected a JSON object."),),
            source_path=resolved_source,
        )

    issues: list[EventDataIssue] = []
    event_id, event_date = _read_event_identity(document, issues=issues)
    embedded_release, format_version = _read_format_metadata(document, issues=issues)
    detector_array, detector_quality_flags = _classify_detector_array(document, issues=issues)
    station_entries = _non_empty_list_value(
        _required_field(document, "stations", parent_location="/", issues=issues),
        location="/stations",
        issues=issues,
    )

    seen_station_ids: set[int] = set()
    station_ids: list[int] = []
    station_names: list[str] = []
    positions_m: list[tuple[float, float, float]] = []
    times_ns: list[float] = []
    uncertainties_ns: list[float] = []
    official_selected_count = 0
    name_fallback_count = 0

    # An invalid list has already added an issue; the final gate will raise it.
    entries_to_check = station_entries if station_entries is not None else []

    for index, raw_station in enumerate(entries_to_check):
        location = _child_location("/stations", index)
        row_issue_count = len(issues)
        station = _mapping_value(raw_station, location=location, issues=issues)
        if station is None:
            continue

        station_id = _integer_value(
            _required_field(station, "id", parent_location=location, issues=issues),
            location=_child_location(location, "id"),
            issues=issues,
            minimum=INT64_MIN,
            maximum=INT64_MAX,
        )

        is_selected = _binary_flag_value(
            _required_field(station, "isSelected", parent_location=location, issues=issues),
            location=_child_location(location, "isSelected"),
            issues=issues,
        )

        if station_id is not None:
            if station_id in seen_station_ids:
                _record_issue(
                    issues,
                    code="duplicate_station_id",
                    location=_child_location(location, "id"),
                    message=f"Station ID {station_id} appears more than once.",
                )
            else:
                seen_station_ids.add(station_id)

        if is_selected is None and policy is StationSelection.OFFICIAL_SELECTED:
            continue
        if is_selected == 1:
            official_selected_count += 1

        if policy is StationSelection.OFFICIAL_SELECTED and is_selected == 0:
            continue  # Do not access excluded names or measurement fields.

        raw_name = _optional_field(station, "name")
        used_name_fallback = raw_name is _MISSING

        if used_name_fallback:
            station_name = str(station_id) if station_id is not None else None
        else:
            station_name = _nonblank_string_value(
                raw_name, location=_child_location(location, "name"), issues=issues
            )

        measurements = _read_station_measurements(station, location=location, issues=issues)

        if (
            len(issues) != row_issue_count
            or station_id is None
            or station_name is None
            or measurements is None
        ):
            continue  # Errors remain recorded; the event cannot pass the final gate.

        position_m, observed_time_ns, timing_uncertainty_ns = measurements
        station_ids.append(station_id)
        station_names.append(station_name)
        positions_m.append(position_m)
        times_ns.append(observed_time_ns)
        uncertainties_ns.append(timing_uncertainty_ns)
        if used_name_fallback:
            name_fallback_count += 1

    # Schema failures take precedence over too-few-stations failures.
    _raise_schema_errors(issues, source_path=resolved_source)

    if (
        event_id is None
        or embedded_release is None
        or format_version is None
        or detector_array is None
        or station_entries is None
    ):
        raise RuntimeError("Adapter validation returned incomplete data without an issue.")

    if len(station_ids) < required_count:
        raise AugerStationSelectionError(
            selection_policy=policy,
            available_stations=len(station_ids),
            required_stations=required_count,
            source_path=resolved_source,
        )

    quality_flags = detector_quality_flags
    if name_fallback_count:
        quality_flags += (f"station_name_fallbacks:{name_fallback_count}",)

    return AugerPlaneFrontInput(
        event_id=event_id,
        canonical_event_id=f"{event_id:012d}",
        embedded_release=embedded_release,
        format_version=format_version,
        event_date=event_date,
        source_path=resolved_source,
        detector_array=detector_array,
        selection_policy=policy,
        triggered_station_count=len(station_entries),
        official_selected_station_count=official_selected_count,
        station_ids=_readonly_integer_array(station_ids),
        station_names=tuple(station_names),
        station_positions_m=_readonly_float_array(positions_m),
        observed_times_ns=_readonly_float_array(times_ns),
        timing_uncertainties_ns=_readonly_float_array(uncertainties_ns),
        quality_flags=quality_flags,
    )


def _read_reference_uncertainty(
    reconstruction: Mapping[str, object], field: str, *, issues: list[EventDataIssue]
) -> float | None:
    """Read an optional, finite, nonnegative angular uncertainty in degrees."""

    raw_value = _optional_field(reconstruction, field)

    if raw_value is _MISSING:
        return None  # An absent uncertainty is unknown, not zero.

    return _finite_float_value(
        raw_value,
        location=_child_location("/sdrec", field),
        issues=issues,
        minimum=0.0,  # Reference metadata may contain zero; station dt may not.
    )


def adapt_auger_direction_reference(
    document: object, *, source_path: str | Path | None = None
) -> AugerDirectionReference:
    """Read Auger's published direction separately from reconstruction inputs.

    Read only event identity, format metadata, and sdrec direction fields.
    Missing angular uncertainties become None; present values must be finite
    and nonnegative. Validate angle ranges before mapping 360 degrees to zero.

    This is an evaluation reference, not known physical truth. source_path
    records provenance only; this function does not open a file.
    """

    resolved_source = None if source_path is None else Path(source_path).expanduser().resolve()

    if not isinstance(document, Mapping):
        raise AugerEventSchemaError(
            (EventDataIssue("wrong_type", "/", "Expected a JSON object."),),
            source_path=resolved_source,
        )

    issues: list[EventDataIssue] = []

    # This output needs the ID, but does not consume or validate info.date.
    event_id, _ = _read_event_identity(document, issues=issues, include_date=False)

    embedded_release, format_version = _read_format_metadata(document, issues=issues)

    reconstruction = _mapping_value(
        _required_field(document, "sdrec", parent_location="/", issues=issues),
        location="/sdrec",
        issues=issues,
    )

    zenith_deg: float | None = None
    azimuth_deg: float | None = None
    zenith_uncertainty_deg: float | None = None
    azimuth_uncertainty_deg: float | None = None

    if reconstruction is not None:
        zenith_deg = _finite_float_value(
            _required_field(reconstruction, "theta", parent_location="/sdrec", issues=issues),
            location="/sdrec/theta",
            issues=issues,
            minimum=0.0,
            maximum=90.0,
        )

        azimuth_deg = _finite_float_value(
            _required_field(reconstruction, "phi", parent_location="/sdrec", issues=issues),
            location="/sdrec/phi",
            issues=issues,
            minimum=0.0,
            maximum=360.0,
        )

        zenith_uncertainty_deg = _read_reference_uncertainty(
            reconstruction,
            "dtheta",
            issues=issues,
        )
        azimuth_uncertainty_deg = _read_reference_uncertainty(
            reconstruction,
            "dphi",
            issues=issues,
        )

    # Reject all recorded schema errors before constructing a successful result.
    _raise_schema_errors(issues, source_path=resolved_source)

    if (
        event_id is None
        or embedded_release is None
        or format_version is None
        or zenith_deg is None
        or azimuth_deg is None
    ):
        raise RuntimeError("Reference validation returned incomplete data without an issue.")

    return AugerDirectionReference(
        event_id=event_id,
        canonical_event_id=f"{event_id:012d}",
        embedded_release=embedded_release,
        format_version=format_version,
        source_path=resolved_source,
        zenith_deg=zenith_deg,
        azimuth_deg=azimuth_deg % 360.0,  # Only a validated 360 becomes zero.
        zenith_uncertainty_deg=zenith_uncertainty_deg,
        azimuth_uncertainty_deg=azimuth_uncertainty_deg,
    )


def _json_object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build one JSON object without silently overwriting duplicate members."""

    result: dict[str, object] = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}.")
        result[key] = value

    return result


def _decode_auger_event_file(source_path: str | Path) -> tuple[object, Path]:
    """Decode one local UTF-8 event file and retain its resolved source path.

    Accept an optional UTF-8 byte-order mark and reject duplicate object keys.
    Preserve filesystem errors. Wrap text/JSON decoding failures with their
    original causes; report line/column only when the JSON parser provides them.

    Scientific validation belongs to the adapters. The decoder retains Python's
    handling of NaN/Infinity; consumed numerical fields must still pass the
    adapters' finite-value checks. This is not a whole-file scientific validator.
    """

    resolved_source = Path(source_path).expanduser().resolve()

    try:
        with resolved_source.open("r", encoding="utf-8-sig") as stream:
            document: object = json.load(
                stream, object_pairs_hook=_json_object_without_duplicate_keys
            )
    except json.JSONDecodeError as error:
        raise AugerEventDecodeError(
            resolved_source, error.msg, line=error.lineno, column=error.colno
        ) from error
    except UnicodeDecodeError as error:
        raise AugerEventDecodeError(resolved_source, "Expected UTF-8 encoded JSON text.") from error
    except ValueError as error:
        # Includes duplicate keys and the interpreter's integer-digit limit.
        raise AugerEventDecodeError(resolved_source, str(error)) from error

    return document, resolved_source


def load_auger_plane_front_input(
    source_path: str | Path,
    *,
    selection: StationSelection | str = StationSelection.OFFICIAL_SELECTED,
    minimum_stations: int = DEFAULT_MINIMUM_STATIONS,
) -> AugerPlaneFrontInput:
    """Load one event file and return validated station inputs, not reference angles."""

    document, resolved_source = _decode_auger_event_file(source_path)

    # Keep adapter calls outside the decoding error handler.
    return adapt_auger_plane_front_input(
        document,
        selection=selection,
        minimum_stations=minimum_stations,
        source_path=resolved_source,
    )


def load_auger_direction_reference(source_path: str | Path) -> AugerDirectionReference:
    """Load Auger's published direction through the separate evaluation adapter."""

    document, resolved_source = _decode_auger_event_file(source_path)

    return adapt_auger_direction_reference(document, source_path=resolved_source)
