# Auger Direction Reconstruction

An undergraduate computational-physics project that reconstructs the arrival
direction of ultra-high-energy cosmic-ray air showers from Pierre Auger surface
detector station positions, signal start times, and signal measurements.

## Scientific question

How accurately can a transparent plane-front timing model reconstruct a shower's
arrival direction, and can a carefully validated machine-learning correction
improve it without using leaked outputs from Auger's official reconstruction?

The project begins with physics and reproducibility. Deployment and an interactive
application belong to Phase 2, after the scientific result is complete.

## Current scope

1. Learn the schema using official example event `081847956000`.
2. Build and validate a plane-front reconstruction on vertical SD-1500 events
   with at least six selected stations.
3. Compare our direction with the released Auger direction using angular error.
4. Add an ML residual correction only after the baseline is trustworthy.
5. Test robustness on different zenith, multiplicity, energy, and detector regimes.

## First setup

```bash
uv sync
uv run auger sources
uv run auger download first-event
uv run auger validate data/raw/events/Auger_081847956000.json
uv run auger inspect data/raw/events/Auger_081847956000.json
uv run auger download summary
uv run auger build-pilot
```

Raw data are deliberately excluded from Git. Each download is recorded in
`data/manifests/downloads.jsonl` with its URL, size, and checksums.

## Repository map

```text
configs/              Versioned data-source and cohort definitions
data/                 Local data areas plus tracked provenance manifests
docs/                 Scientific decisions, field policy, and learning notes
notebooks/            Exploration only; reusable logic belongs in src/
reports/figures/       Final, reproducible scientific figures
src/auger_reco/data/   Downloading, parsing, and validation
src/auger_reco/physics/Geometry and reconstruction models
src/auger_reco/evaluation/Angular metrics and validation
src/auger_reco/ml/     Later residual-correction models
tests/                 Small deterministic tests
```

## Authoritative data source

Pierre Auger Open Data, Release 3 (20 March 2024):

- Portal: <https://opendata.auger.org/>
- Dataset DOI: <https://doi.org/10.5281/zenodo.4487612>
- Release DOI: <https://doi.org/10.5281/zenodo.10488964>

See `docs/data_strategy.md` before downloading the full event archive.
