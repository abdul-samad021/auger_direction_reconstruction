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
