"""Read a published Auger core separately from blind station measurements.

The official field table at https://opendata.auger.org/data.php describes
``sdrec.x/y/z`` as core coordinates in the site coordinate system, in metres,
and ``sdrec.dx/dy`` as their coordinate uncertainties, also in metres. This
module preserves those Cartesian values without a UTM conversion, terrain
adjustment, or additional Earth-curvature correction. It does not establish
the undocumented details of the coordinate export transformation.

A fit supplied with this reference is **Auger-core-assisted**, not independent
of Auger's reconstruction. No official angle, radius, signal, or reconstructed
station distance is read into the result. The optional x/y uncertainties do
not define a covariance matrix: axis offsets based on them are sensitivity
checks, not confidence regions or independent Gaussian core simulations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from auger_reco.data import event_json

type FloatArray = NDArray[np.float64]

CORE_DOCUMENTATION_URL = "https://opendata.auger.org/data.php"


@dataclass(frozen=True, slots=True)
class AugerCoreReference:
    """Validated official core and provenance, separate from fitting inputs.

    ``position_m`` has shape ``(3,)`` in x/y/z order. Missing uncertainty
    fields become ``None``; present uncertainties must be strictly positive.
    This positivity requirement is our sensitivity-study input contract, not
    a claim that every released event must contain a nonzero uncertainty.
    There is no inferred z uncertainty or x/y correlation. The embedded
    release label is not the portal's public-release number.
    """

    event_id: int
    canonical_event_id: str
    embedded_release: str
    format_version: int
    source_path: Path | None
    position_m: FloatArray
    uncertainty_x_m: float | None
    uncertainty_y_m: float | None
    source: Literal["sdrec"] = field(default="sdrec", init=False)
    position_field_paths: tuple[str, ...] = field(
        default=("/sdrec/x", "/sdrec/y", "/sdrec/z"), init=False
    )
    uncertainty_field_paths: tuple[str, ...] = field(default=("/sdrec/dx", "/sdrec/dy"), init=False)
    coordinate_frame: str = field(default="released site coordinates", init=False)
    documentation_url: str = field(default=CORE_DOCUMENTATION_URL, init=False)


def adapt_auger_core_reference(
    document: object, *, source_path: str | Path | None = None
) -> AugerCoreReference:
    """Validate identity, format, and core fields without inspecting directions.

    This in-memory adapter opens no files. Errors use the existing event
    adapter's structured issue types, paths, and metadata rules. Its internal
    validation primitives are intentionally shared here so strict JSON-number
    and format-version semantics cannot diverge between reference loaders.
    Other reconstruction fields and station measurements remain unconsumed.
    """

    resolved_source = None if source_path is None else Path(source_path).expanduser().resolve()
    if not isinstance(document, Mapping):
        raise event_json.AugerEventSchemaError(
            (event_json.EventDataIssue("wrong_type", "/", "Expected a JSON object."),),
            source_path=resolved_source,
        )

    issues: list[event_json.EventDataIssue] = []
    event_id, _ = event_json._read_event_identity(document, issues=issues, include_date=False)
    embedded_release, format_version = event_json._read_format_metadata(document, issues=issues)
    reconstruction = event_json._mapping_value(
        event_json._required_field(document, "sdrec", parent_location="/", issues=issues),
        location="/sdrec",
        issues=issues,
    )
    coordinates: list[float | None] = []
    uncertainties: list[float | None] = []
    if reconstruction is not None:
        for name in ("x", "y", "z"):
            coordinates.append(
                event_json._finite_float_value(
                    event_json._required_field(
                        reconstruction, name, parent_location="/sdrec", issues=issues
                    ),
                    location=f"/sdrec/{name}",
                    issues=issues,
                )
            )
        for name in ("dx", "dy"):
            raw_value = event_json._optional_field(reconstruction, name)
            uncertainties.append(
                None
                if raw_value is event_json._MISSING
                else event_json._finite_float_value(
                    raw_value,
                    location=f"/sdrec/{name}",
                    issues=issues,
                    strictly_positive=True,
                )
            )

    event_json._raise_schema_errors(issues, source_path=resolved_source)
    if (
        event_id is None
        or embedded_release is None
        or format_version is None
        or len(coordinates) != 3
        or any(value is None for value in coordinates)
        or len(uncertainties) != 2
    ):
        raise RuntimeError("Core validation returned incomplete data without an issue.")

    # An immutable byte buffer prevents both assignment and re-enabling writes.
    position_m = np.frombuffer(
        np.asarray(coordinates, dtype=np.float64).tobytes(), dtype=np.float64
    )
    return AugerCoreReference(
        event_id=event_id,
        canonical_event_id=f"{event_id:012d}",
        embedded_release=embedded_release,
        format_version=format_version,
        source_path=resolved_source,
        position_m=position_m,
        uncertainty_x_m=uncertainties[0],
        uncertainty_y_m=uncertainties[1],
    )


def load_auger_core_reference(source_path: str | Path) -> AugerCoreReference:
    """Load a core reference with strict UTF-8/duplicate-key JSON decoding.

    Filesystem errors propagate; malformed text uses ``AugerEventDecodeError``;
    consumed-field problems use ``AugerEventSchemaError``. This function does
    not call the direction-reference loader or place core values into the
    blind plane-front adapter. Record the complete source-file hash separately
    when freezing an experiment's provenance.
    """

    document, resolved_source = event_json._decode_auger_event_file(source_path)
    return adapt_auger_core_reference(document, source_path=resolved_source)
