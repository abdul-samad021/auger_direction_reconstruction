# Data acquisition, selection, and validation

## Authoritative release

Use only the Pierre Auger Open Data portal and its Zenodo Release 3 record.
The release contains 81,121 showers as per-event pseudo-raw JSON and reconstructed
summary CSV files. The JSON archive is about 826 MB; the summary archive is about
8 MB. Release files and checksums are versioned in `configs/data_sources.toml`.

## Staged acquisition

### Stage A: one documented event

Download event `081847956000`, which the Auger documentation uses as an example.
It has many stations and is useful for learning, plotting, and debugging. Because
it is a deliberately interesting high-energy event, never use it alone to claim
general performance.

### Stage B: summary and auxiliary archives

Use the summary tables to learn the released population, deduplicate multi-eye
rows by event ID, and build a deterministic cohort manifest. Use auxiliary station
tables to cross-check coordinates. These archives have published Zenodo MD5 sums.

### Stage C: pilot event cohort

Start with 1,000 vertical SD-1500 events having at least six selected stations.
Stratify across zenith, multiplicity, and energy so the pilot is not dominated by
the easiest events. Freeze IDs before evaluating alternative reconstructions.

The Release 3 audit found 24,319 SD-1500 summary rows representing 24,285 unique
events. After removing 34 repeated multi-eye rows, 10,081 unique events satisfy
the initial zenith and multiplicity rule, with no missing direction targets.

### Stage D: final and robustness cohorts

Scale to all eligible vertical SD-1500 events after the parser and baseline pass.
Then test, rather than silently mix, SD-750 and inclined SD-1500 events. Detector
spacing and inclined-shower physics make these meaningful distribution shifts.

## Validation gates

1. **Provenance:** official URL, DOI, release, retrieval time, byte size, MD5, and
   SHA-256 are recorded.
2. **Archive integrity:** ZIP central directory and every member pass an integrity
   check; unsafe paths are rejected before extraction.
3. **Schema:** required event sections and station fields exist with expected types.
4. **Physical consistency:** coordinates and times are finite, signals are
   non-negative, IDs are unique, and selected stations span space and time.
5. **Population checks:** event counts, array flags, multiplicity, zenith, energy,
   missingness, and duplicate IDs are summarized before filtering.
6. **Leakage audit:** official direction, core, curvature, fit quality, energy, and
   derived station distances do not enter the reconstruction features.
7. **Split integrity:** all representations of one event stay in one split; test
   IDs remain untouched until the method is frozen.
8. **Visual checks:** a small fixed event set receives footprint, time, residual,
   and trace plots to catch convention and unit mistakes.

## Commands

```bash
uv run auger download first-event
uv run auger download summary
uv run auger download auxiliary
uv run auger validate data/raw/events/Auger_081847956000.json
uv run auger validate data/raw/archives/summary.zip
uv run auger build-pilot
```

The full archive requires an explicit acknowledgement:

```bash
uv run auger download full-events --allow-large
```
