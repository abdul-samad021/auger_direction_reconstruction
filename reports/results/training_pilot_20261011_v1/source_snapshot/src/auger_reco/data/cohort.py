from __future__ import annotations

import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from auger_reco.data.sources import PROJECT_ROOT

SUMMARY_ARCHIVE = PROJECT_ROOT / "data" / "raw" / "archives" / "summary.zip"
SUMMARY_MEMBER = "summary/dataSummarySD1500.csv"
COHORT_CONFIG = PROJECT_ROOT / "configs" / "pilot_cohort.toml"
OUTPUT_CSV = PROJECT_ROOT / "data" / "manifests" / "pilot_sd1500_vertical_v1.csv"
OUTPUT_AUDIT = PROJECT_ROOT / "data" / "manifests" / "pilot_sd1500_vertical_v1.audit.json"
CONSISTENCY_FIELDS = ["sd_theta", "sd_phi", "sd_energy", "sd_nbstat"]


def _hash_rank(event_id: int, seed: int, namespace: str) -> int:
    payload = f"{namespace}:{seed}:{event_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _split_for_event(
    event_id: int,
    seed: int,
    train_fraction: float,
    validation_fraction: float,
) -> str:
    rank = _hash_rank(event_id, seed, "split") / 2**64
    if rank < train_fraction:
        return "train"
    if rank < train_fraction + validation_fraction:
        return "validation"
    return "test"


def _check_duplicate_consistency(frame: pd.DataFrame) -> None:
    duplicates = frame[frame.duplicated("id", keep=False)]
    if duplicates.empty:
        return
    inconsistent = (
        duplicates.groupby("id")[CONSISTENCY_FIELDS].nunique(dropna=False).gt(1).any(axis=1)
    )
    if inconsistent.any():
        examples = inconsistent[inconsistent].index.tolist()[:5]
        raise ValueError(f"Repeated event rows disagree in SD fields: {examples}")


def _add_strata(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["zenith_bin"] = pd.cut(
        result["sd_theta"],
        bins=[0, 15, 30, 45, 60.000001],
        labels=["0-15", "15-30", "30-45", "45-60"],
        include_lowest=True,
    )
    result["multiplicity_bin"] = pd.cut(
        result["sd_nbstat"],
        bins=[5.999, 7.999, 11.999, np.inf],
        labels=["6-7", "8-11", "12+"],
        include_lowest=True,
    )
    result["energy_bin"] = pd.qcut(
        np.log10(result["sd_energy"]),
        q=4,
        labels=["q1", "q2", "q3", "q4"],
    )
    result["stratum"] = (
        result["zenith_bin"].astype(str)
        + "|"
        + result["multiplicity_bin"].astype(str)
        + "|"
        + result["energy_bin"].astype(str)
    )
    return result


def _balanced_stratified_sample(frame: pd.DataFrame, count: int, seed: int) -> pd.DataFrame:
    ranked = frame.copy()
    ranked["_rank"] = [_hash_rank(int(event_id), seed, "pilot") for event_id in ranked["id"]]
    groups = [
        group.sort_values("_rank").reset_index(drop=True)
        for _, group in ranked.groupby("stratum", observed=True, sort=True)
    ]
    selected_rows: list[pd.Series] = []
    for position in range(max(len(group) for group in groups)):
        for group in groups:
            if position < len(group):
                selected_rows.append(group.iloc[position])
                if len(selected_rows) == count:
                    return pd.DataFrame(selected_rows)
    raise ValueError(f"Requested {count} events but only {len(selected_rows)} are available")


def build_pilot_cohort(
    summary_archive: Path = SUMMARY_ARCHIVE,
    config_path: Path = COHORT_CONFIG,
    output_csv: Path = OUTPUT_CSV,
    output_audit: Path = OUTPUT_AUDIT,
) -> dict[str, object]:
    if not summary_archive.is_file():
        raise FileNotFoundError("Download the summary source before building the pilot cohort.")

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    with zipfile.ZipFile(summary_archive) as archive:
        with archive.open(SUMMARY_MEMBER) as handle:
            summary = pd.read_csv(handle)

    _check_duplicate_consistency(summary)
    unique = summary.drop_duplicates("id", keep="first").copy()
    filters = config["filters"]
    eligible = unique[
        (unique["sd1500"] == filters["sd1500_flag"])
        & unique["sd_theta"].between(
            filters["zenith_min_deg"], filters["zenith_max_deg"], inclusive="both"
        )
        & (unique["sd_nbstat"] >= filters["min_selected_stations"])
        & unique[["sd_theta", "sd_phi"]].notna().all(axis=1)
    ].copy()

    sampling = config["sampling"]
    eligible = _add_strata(eligible)
    pilot = _balanced_stratified_sample(
        eligible,
        count=int(sampling["pilot_events"]),
        seed=int(sampling["seed"]),
    )

    split = config["split"]
    pilot["split"] = [
        _split_for_event(
            int(event_id),
            int(sampling["seed"]),
            float(split["train_fraction"]),
            float(split["validation_fraction"]),
        )
        for event_id in pilot["id"]
    ]
    pilot["event_id"] = pilot["id"].astype("int64")
    output = pilot[
        [
            "event_id",
            "split",
            "sd_theta",
            "sd_phi",
            "sd_energy",
            "sd_nbstat",
            "zenith_bin",
            "multiplicity_bin",
            "energy_bin",
            "stratum",
        ]
    ].rename(
        columns={
            "sd_theta": "reference_theta_deg",
            "sd_phi": "reference_phi_deg",
            "sd_energy": "reference_energy_eev",
            "sd_nbstat": "selected_stations",
        }
    )
    output = output.sort_values("event_id").reset_index(drop=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_csv, index=False)
    audit: dict[str, object] = {
        "cohort": config["name"],
        "release": config["release"],
        "summary_rows": len(summary),
        "unique_events": len(unique),
        "duplicate_rows_removed": len(summary) - len(unique),
        "eligible_events": len(eligible),
        "pilot_events": len(output),
        "split_counts": output["split"].value_counts().sort_index().to_dict(),
        "strata": int(output["stratum"].nunique()),
        "missing_direction_targets": int(
            output[["reference_theta_deg", "reference_phi_deg"]].isna().any(axis=1).sum()
        ),
        "selection_sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest(),
    }
    output_audit.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit
