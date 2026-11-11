from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_CONFIG = PROJECT_ROOT / "configs" / "data_sources.toml"


@dataclass(frozen=True)
class DataSource:
    name: str
    description: str
    url: str
    relative_path: Path
    expected_bytes: int
    expected_md5: str | None
    large: bool

    @classmethod
    def from_mapping(cls, name: str, values: dict[str, Any]) -> DataSource:
        expected_md5 = str(values.get("expected_md5", "")).strip() or None
        return cls(
            name=name,
            description=str(values["description"]),
            url=str(values["url"]),
            relative_path=Path(str(values["relative_path"])),
            expected_bytes=int(values.get("expected_bytes", 0)),
            expected_md5=expected_md5,
            large=bool(values.get("large", False)),
        )


def load_sources(config_path: Path = SOURCE_CONFIG) -> dict[str, DataSource]:
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    return {
        name: DataSource.from_mapping(name, values) for name, values in config["sources"].items()
    }
