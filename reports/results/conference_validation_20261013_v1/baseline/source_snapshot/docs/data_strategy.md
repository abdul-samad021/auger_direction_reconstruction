# Data acquisition, selection, and validation

Last reviewed: 2026-09-15

This document governs acquisition and cohort handling for the
[14-stage research roadmap](research_roadmap.md), particularly Stages 2–4, 6,
10, and 13. The lettered acquisition steps below are not additional research stages.

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

Its released direction has already been inspected, so it is unblinded development
data. A reference-hidden demonstration requires a different predeclared event.
The 10–20-event integration cohort also belongs to development, not a protected
test set.

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

Preserve the existing pilot identifiers and split history. The current manifest
contains reference values as well as split assignments; Stage 4 requires a
target-free execution manifest and a separately controlled reference store before
batch evaluation. Do not rerun cohort construction to obtain a more favourable
sample after inspecting model performance.

The initial population rule uses official event classifications and selected
station counts. An independent-selector study within this pilot remains conditional
on that cohort definition. Predeclare any broader population study separately;
do not imply that removing `isSelected` from model inputs undoes all release or
cohort selection.

### Stage D: final and robustness cohorts

Before expanding beyond development data, reserve a non-overlapping final benchmark
and define any intermediate release-specific evaluation cohorts. Preserve the
reserved data while scaling to a larger justified vertical SD-1500 cohort.
An all-eligible descriptive analysis can follow the primary frozen evaluation,
but must not be presented as a new untouched test.

Test, rather than silently mix, SD-750 and inclined SD-1500 events. Detector
spacing and inclined-shower physics make these meaningful distribution shifts;
do not assume a method validated on the vertical cohort is validated near the
horizon or on another array.

### Stage E: simulations and independent references

Maintain separate provenance and evaluation records for:

1. controlled synthetic station measurements with known generated directions;
2. particle-level air-shower simulations with explicit detector approximations;
3. realistic detector-level simulated events with known truth;
4. official or independent reconstructions used as comparison references.

A useful reconstruction-validation sample needs station positions, measured or
simulated start times, timing uncertainties, and relevant trigger/selection
information in addition to the true direction. A matched official comparison
also needs comparable Auger reconstructions of the same events. No ready-to-use
public sample satisfying these requirements has yet been verified; record access
requests, terms, simulator/calibration versions, and unresolved dependencies.

Group repeated views and noise/detector realizations of the same simulated shower
when evaluating generalization. Record scenario settings and random seeds. Keep
the completed fixed-geometry noise experiment distinct from studies of different
showers, geometries, detector responses, or simulation-to-data transfer.

## Reference quarantine and evaluation lifecycle

- Classify fields as reconstruction inputs, diagnostics, selection assistance,
  cohort metadata, or evaluation targets using the [field policy](field_policy.md).
- Keep official directions and other prohibited reconstructed features out of the
  execution manifest and model input path. Merely omitting them from a plot or
  promising not to inspect them is not technical separation.
- Record prior exposure to targets; an already inspected example cannot be relabelled
  as blinded. Use development/validation results for model and quality-cut choices.
- Freeze preprocessing, features, selection, model settings, uncertainty calibration,
  exclusions, metrics, and statistical procedures before opening a test cohort.
- Record predictions and their provenance before reference evaluation. Once test
  results are viewed, retain that cohort as historical, not untouched evidence
  for later changes.
- Report event-level success, failure, exclusion, and abstention counts over the
  eligible cohort, with paired accuracy on common successful events separately.

## Coordinate and metadata provenance

Preserve completed local-axis and sky-arrival convention checks. Separately document
the exact public station-coordinate export frame, origin, height datum, and Earth
curvature treatment as those details are resolved. Do not modify coordinates with
an assumed Earth-curvature correction or treat signal-start times as already
flattened for shower-front curvature. Keep unanswered questions explicit and
quantify sensitivities before adopting corrections.

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
   targets remain quarantined until the procedure is frozen. Group related
   simulated realizations appropriately and audit prior exposure.
8. **Visual checks:** a small fixed event set receives footprint, time, residual,
   and trace plots to catch convention and unit mistakes.

## Commands

These are acquisition/construction commands, not instructions to rebuild the
already-frozen pilot or open protected references during model development.

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
