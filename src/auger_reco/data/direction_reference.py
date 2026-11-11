"""Compare released Auger angles with fits in the central-site ENU frame.

The 2026-10-14 redundant-field audit supports interpreting ``sdrec.theta/phi``
in the core-local east/north/up (ENU) basis, while released station XYZ and our
fitted vectors use central-site ENU. This is empirical export evidence, not an
inspection of Auger's exporter source or an independent pointing calibration.

Only evaluation references are rotated here. Station measurements and fitted
timing parameters are untouched. Call this loader after freezing predictions;
the published core is used to identify the reference's basis, not as a fit input.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pyproj
from numpy.typing import NDArray
from pyproj import Transformer
from pyproj.exceptions import ProjError

from auger_reco.data import event_json

type FloatArray = NDArray[np.float64]

DIRECTION_FRAME_VERSION = "auger-core-enu-to-site-enu-wgs84-v1"
SITE_ORIGIN_EASTING_M = 477256.66
SITE_ORIGIN_NORTHING_M = 6099203.68
SITE_ORIGIN_ALTITUDE_M = 1400.0
CORE_COORDINATE_CRS = "EPSG:32719"


@dataclass(frozen=True, slots=True)
class SiteDirectionReference:
    """Published angles plus a common-frame sky vector and audit provenance.

    ``reference`` retains the unmodified, core-local published angles and their
    uncertainties. They must not be labeled site-frame angles. The immutable
    ``sky_direction_site`` is the vector to compare with our fitted sky vector.
    This rotation does not propagate the angular uncertainties or claim that
    they describe a covariance matrix.
    """

    reference: event_json.AugerDirectionReference
    sky_direction_site: FloatArray
    core_easting_m: float
    core_northing_m: float
    core_longitude_deg: float
    core_latitude_deg: float

    @property
    def frame_metadata(self) -> dict[str, object]:
        """Return fresh, JSON-serializable provenance without mutable shared state."""

        longitude, latitude = _site_origin_geodetic()
        return {
            "method_version": DIRECTION_FRAME_VERSION,
            "native_reference_frame": "core-local WGS84 geodetic ENU",
            "comparison_frame": "central-site WGS84 geodetic ENU",
            "vector_convention": "sky-arrival unit vector; east, north, up",
            "rotation": "B_site.T @ B_core @ sky_core; ENU columns in ECEF",
            "core_coordinate_crs": CORE_COORDINATE_CRS,
            "core_easting_m": self.core_easting_m,
            "core_northing_m": self.core_northing_m,
            "core_longitude_deg": self.core_longitude_deg,
            "core_latitude_deg": self.core_latitude_deg,
            "site_origin": {
                "easting_m": SITE_ORIGIN_EASTING_M,
                "northing_m": SITE_ORIGIN_NORTHING_M,
                "reported_altitude_m": SITE_ORIGIN_ALTITUDE_M,
                "longitude_deg": longitude,
                "latitude_deg": latitude,
            },
            "consumed_coordinate_fields": ["/sdrec/easting", "/sdrec/northing"],
            "pyproj_version": pyproj.__version__,
            "proj_version": pyproj.proj_version_str,
            "evidence": "released redundant-field audit; not exporter-source verification",
            "angular_uncertainties": "native values preserved; covariance not propagated",
        }


@lru_cache(maxsize=1)
def _utm_to_geodetic() -> Transformer:
    """Use longitude/latitude order explicitly; no network/grid datum lookup."""

    return Transformer.from_crs(CORE_COORDINATE_CRS, "EPSG:4326", always_xy=True)


@lru_cache(maxsize=1)
def _site_origin_geodetic() -> tuple[float, float]:
    """Derive the fixed origin from the exact supplied UTM values, not a rounded latitude."""

    longitude, latitude = _utm_to_geodetic().transform(
        SITE_ORIGIN_EASTING_M, SITE_ORIGIN_NORTHING_M, errcheck=True
    )
    return float(longitude), float(latitude)


def _enu_basis(longitude_deg: float, latitude_deg: float) -> FloatArray:
    """Return right-handed ENU columns in ECEF using WGS84 geodetic latitude.

    Multiplication by this orthogonal matrix expresses a local vector in ECEF;
    multiplication by its transpose projects an ECEF vector onto local ENU.
    Altitude changes the origin but not these directions, so it is not required
    for this free-vector rotation. No station translation or Earth sag is added.
    """

    longitude, latitude = np.deg2rad([longitude_deg, latitude_deg])
    return np.column_stack(
        (
            [-np.sin(longitude), np.cos(longitude), 0.0],
            [
                -np.sin(latitude) * np.cos(longitude),
                -np.sin(latitude) * np.sin(longitude),
                np.cos(latitude),
            ],
            [
                np.cos(latitude) * np.cos(longitude),
                np.cos(latitude) * np.sin(longitude),
                np.sin(latitude),
            ],
        )
    )


def adapt_auger_site_direction_reference(
    document: object, *, source_path: str | Path | None = None
) -> SiteDirectionReference:
    """Validate native reference/core coordinates and rotate into the fit frame.

    Missing, nonfinite, boolean, or out-of-zone coordinates fail closed using
    ``AugerEventSchemaError``. There is deliberately no native-angle fallback.
    A missing altitude is acceptable: a vector-basis rotation does not need it.
    Input documents are never mutated, and this in-memory adapter performs no I/O.
    """

    reference = event_json.adapt_auger_direction_reference(document, source_path=source_path)
    # The native adapter has already established that these parents are mappings.
    reconstruction = document["sdrec"]
    issues: list[event_json.EventDataIssue] = []
    coordinates: list[float | None] = []
    for name, minimum, maximum in (
        ("easting", 100000.0, 900000.0),
        ("northing", 0.0, 10000000.0),
    ):
        coordinates.append(
            event_json._finite_float_value(
                event_json._required_field(
                    reconstruction, name, parent_location="/sdrec", issues=issues
                ),
                location=f"/sdrec/{name}",
                issues=issues,
                minimum=minimum,
                maximum=maximum,
            )
        )
    event_json._raise_schema_errors(issues, source_path=reference.source_path)
    easting, northing = coordinates
    if easting is None or northing is None:
        raise RuntimeError("Coordinate validation returned incomplete data without an issue.")

    try:
        longitude, latitude = _utm_to_geodetic().transform(easting, northing, errcheck=True)
    except ProjError as error:
        raise event_json.AugerEventSchemaError(
            (event_json.EventDataIssue("invalid_coordinate", "/sdrec", str(error)),),
            source_path=reference.source_path,
        ) from error
    if (
        not np.isfinite([longitude, latitude]).all()
        or not -72.0 <= longitude <= -66.0
        or not -80.0 <= latitude <= 0.0
    ):
        raise event_json.AugerEventSchemaError(
            (
                event_json.EventDataIssue(
                    "out_of_range",
                    "/sdrec",
                    "Core coordinates must lie within WGS84 UTM zone 19 south.",
                ),
            ),
            source_path=reference.source_path,
        )

    theta, phi = np.deg2rad([reference.zenith_deg, reference.azimuth_deg])
    sky_core = np.array(
        [np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)],
        dtype=np.float64,
    )
    site_basis = _enu_basis(*_site_origin_geodetic())
    core_basis = _enu_basis(longitude, latitude)
    sky_site = site_basis.T @ core_basis @ sky_core
    # The orthogonal transform preserves length; do not insert an empirical angle offset.
    immutable_sky = np.frombuffer(sky_site.tobytes(), dtype=np.float64)
    return SiteDirectionReference(
        reference=reference,
        sky_direction_site=immutable_sky,
        core_easting_m=easting,
        core_northing_m=northing,
        core_longitude_deg=float(longitude),
        core_latitude_deg=float(latitude),
    )


def load_auger_site_direction_reference(source_path: str | Path) -> SiteDirectionReference:
    """Read a strict JSON file and return a reference in the fitted-vector frame.

    Uses the shared decoder, including duplicate-key rejection and useful UTF-8
    errors. Source-file hashing and frozen-prediction checks remain the calling
    experiment's responsibility, exactly as for the native reference loader.
    """

    document, resolved_source = event_json._decode_auger_event_file(source_path)
    return adapt_auger_site_direction_reference(document, source_path=resolved_source)
