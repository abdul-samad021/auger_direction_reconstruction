# Data layout

The contents of `raw/`, `interim/`, and `processed/` are intentionally ignored by
Git. They must be reproducible from versioned code, configuration, and manifests.

- `raw/events/`: unchanged per-event JSON files downloaded from Auger.
- `raw/archives/`: unchanged official ZIP downloads.
- `interim/`: extracted or normalized representations that can be regenerated.
- `processed/`: analysis tables and model-ready features that can be regenerated.
- `manifests/downloads.jsonl`: tracked provenance records created by the downloader.

Never manually edit a file in `raw/`. If a download changes, preserve the source
URL, timestamp, size, and checksums in the manifest and investigate the release.

