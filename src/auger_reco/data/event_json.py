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
from numpy.typing import NDArray

# Reusable type annotations for the NumPy arrays returned by this adapter.
type FloatArray = NDArray[np.float64]
type IntegerArray = NDArray[np.int64]

# Four stations give our three-parameter constrained fit at least one residual degree of freedom.
DEFAULT_MINIMUM_STATIONS = 4

# We have inspected and tested Auger's event JSON format version 2.
SUPPORTED_FORMAT_VERSIONS = frozenset({2})

# Station IDs will later be stored in an np.int64 array. 
# These limits let us reject impossible values with a clear schema error before NumPy conversion.
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

@dataclass(frozen = True, slots = True)
class EventDataIssue:
    """One stable, machine-readable problem found in an event document."""
    code: str
    location: str
    message: str

class AugerEventDataError(ValueError):
    """Base exception for invalid Pierre Auger event data."""

class AugerEventDecodeError(AugerEventDataError):
    """Raised when a file cannot be decoded as JSON text."""

    def __init__(self, source_path: Path, message: str, *, line: int | None = None,
                 column: int | None = None) -> None:
        # Save structured information for tests, logs, and the future web API.
        self.source_path = source_path
        self.line = line
        self.column = column

        # Include the location only when both values are available.
        location = (f"at line {line}, column {column}" if line is not None and column is not None else "")

        # Initialize the inherited ValueError message.
        super().__init__(f"Could not decode Auger event JSON {source_path}{location}: {message}")

class AugerEventSchemaError (AugerEventDataError):
    """Raised when decoded JSON violates the fitter-ready event contract."""

    def __init__(self, issues: tuple[EventDataIssue, ...], *, source_path: Path | None = None) -> None:
        # A schema exception without any reported issue would be a programming mistake in our own adapter.

        if not issues:
            raise ValueError("AugerEventSchemaError requires at least one issue.")

        self.issues = issues
        self.source_path = source_path

        # Use a readable fallback when adapting an in-memory dictionary.
        source = (str(source_path) if source_path is not None else "in-memory event")

        # Convert every structured issue into one readable piece of text.
        details = "; ".join(f"{issue.code} at {issue.location}: {issue.message}" for issue in issues)

        super().__init__(f"Invalid Auger event data in {source}: {details}")

class AugerStationSelectionError(AugerEventDataError):
    """Raised when a station policy yields too few measurements for fitting."""

    def __init__(self, *, selection_policy: StationSelection, available_stations: int, required_stations: int, source_path: Path | None = None) -> None:
        self.selection_policy = selection_policy
        self.available_stations = available_stations
        self.required_stations = required_stations
        self.source_path = source_path

        source = (str(source_path) if source_path is not None else "in-memory event")

        super().__init__(f"Station policy {selection_policy.value!r} selected"
                         f"{available_stations} stations from {source}; at least {required_stations} are required."
                         )