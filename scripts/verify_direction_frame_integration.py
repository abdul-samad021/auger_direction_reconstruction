"""Check the production reference loader against the frozen 712-event frame audit.

No fitting, downloading, protected-event access, or historical writes occur.
This is a regression check against already verified results, not new physics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from auger_reco.data.direction_reference import (
    DIRECTION_FRAME_VERSION,
    load_auger_site_direction_reference,
)
from auger_reco.physics.plane_front import angular_separation_deg

AUDIT = Path("reports/results/exported_direction_frame_20261014_v2")
BASELINE = Path("reports/results/training_pilot_20261011_v1")
FOCUS = "081847956000"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path) -> dict:
    """Reproduce every saved comparison using the new production loader."""
    audit = root / AUDIT
    artifact_hashes = json.loads((audit / "artifact_sha256.json").read_bytes())
    for relative, expected in artifact_hashes.items():
        path = (audit / relative).resolve()
        if not path.is_relative_to(audit.resolve()) or digest(path) != expected:
            raise ValueError(f"Frozen audit artifact changed: {relative}")
    config = json.loads((root / BASELINE / "configuration.json").read_bytes())
    encoded = json.dumps(config["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(encoded.encode()).hexdigest() != config["sha256"]:
        raise ValueError("Frozen training configuration changed.")
    authorized = set(config["payload"]["training_ids"])
    if len(authorized) != 711 or FOCUS in authorized:
        raise ValueError("Authorized already-observed population changed.")
    authorized.add(FOCUS)
    input_hashes = json.loads((audit / "input_sha256.json").read_bytes())
    with (audit / "saved_fit_reference_comparisons.csv").open(newline="") as stream:
        records = list(csv.DictReader(stream))
    identities = {r["event_id"] for r in records}
    if identities != authorized or len(records) != 2848:
        raise ValueError("Audit records do not match the authorized population.")
    expected_keys = {
        (identity, model, weighting)
        for identity in authorized
        for model in ("plane", "quadratic")
        for weighting in ("timing", "uniform")
    }
    if {(r["event_id"], r["model"], r["weighting"]) for r in records} != expected_keys:
        raise ValueError("Missing or duplicate comparison.")
    references = {}
    for identity in sorted(authorized):
        relative = Path("data/raw/events") / f"Auger_{identity}.json"
        path = root / relative
        expected = input_hashes[str(relative)]
        if digest(path) != expected:
            raise ValueError(f"Frozen raw input changed: {identity}")
        references[identity] = load_auger_site_direction_reference(path)
        if (
            references[identity].reference.canonical_event_id != identity
            or digest(path) != expected
        ):
            raise ValueError(f"Reference identity or raw input changed: {identity}")
    differences = []
    for row in records:
        fitted = np.array([float(row[f"fitted_sky_site_{axis}"]) for axis in "xyz"])
        calculated = angular_separation_deg(fitted, references[row["event_id"]].sky_direction_site)
        saved = float(row["core_local_interpretation_separation_deg"])
        differences.append(abs(calculated - saved))
        np.testing.assert_allclose(calculated, saved, rtol=0, atol=1e-10)
    for relative, expected in artifact_hashes.items():
        if digest(audit / relative) != expected:
            raise ValueError("Frozen audit artifact changed during verification.")
    return {
        "status": "passed",
        "direction_frame_version": DIRECTION_FRAME_VERSION,
        "events": len(authorized),
        "training_events": 711,
        "focus_events": 1,
        "comparisons": len(records),
        "maximum_difference_from_verified_separation_deg": max(differences),
        "absolute_tolerance_deg": 1e-10,
        "protected_event_files_opened": 0,
        "fits_executed": 0,
        "historical_artifacts_unchanged": True,
        "artifact_hashes_checked": artifact_hashes,
        "source_sha256": {
            relative: digest(root / relative)
            for relative in (
                "src/auger_reco/data/direction_reference.py",
                "src/auger_reco/physics/plane_front.py",
                "scripts/verify_direction_frame_integration.py",
                "pyproject.toml",
                "uv.lock",
            )
        },
        "interpretation": "Production integration regression, not independent truth validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = verify(args.root.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("sha256")}, indent=2))


if __name__ == "__main__":
    main()
