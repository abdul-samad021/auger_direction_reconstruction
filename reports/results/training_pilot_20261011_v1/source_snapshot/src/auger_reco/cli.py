from __future__ import annotations

import argparse
import json
from pathlib import Path

from auger_reco.data.cohort import build_pilot_cohort
from auger_reco.data.download import download_source
from auger_reco.data.sources import load_sources
from auger_reco.data.validate import inspect_event, validate_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auger",
        description="Reproducible tools for the Auger direction-reconstruction project.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sources", help="List official data sources configured for the project.")

    download = subparsers.add_parser("download", help="Download and checksum one official source.")
    download.add_argument("source", help="Source name shown by the sources command.")
    download.add_argument(
        "--allow-large",
        action="store_true",
        help="Explicitly permit a source marked as large.",
    )

    validate = subparsers.add_parser("validate", help="Validate an event JSON or ZIP archive.")
    validate.add_argument("path", type=Path)

    inspect = subparsers.add_parser("inspect", help="Print a concise event summary.")
    inspect.add_argument("path", type=Path)

    subparsers.add_parser(
        "build-pilot",
        help="Build the frozen SD-1500 pilot cohort from the official summary.",
    )

    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.command == "sources":
        for name, source in load_sources().items():
            size = (
                f"{source.expected_bytes / 1_000_000:.1f} MB"
                if source.expected_bytes
                else "variable"
            )
            marker = " [large]" if source.large else ""
            print(f"{name:12} {size:>10}{marker}  {source.description}")
        return

    if args.command == "download":
        result = download_source(args.source, allow_large=args.allow_large)
        print(json.dumps(result, indent=2))
        return

    if args.command == "validate":
        report = validate_path(args.path)
        print(json.dumps(report, indent=2))
        return

    if args.command == "inspect":
        report = inspect_event(args.path)
        print(json.dumps(report, indent=2))
        return

    if args.command == "build-pilot":
        report = build_pilot_cohort()
        print(json.dumps(report, indent=2))
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
