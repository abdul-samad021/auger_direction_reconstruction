# Auger Direction Reconstruction

An active undergraduate computational-physics project for reconstructing the
arrival direction of ultra-high-energy cosmic-ray air showers from Pierre Auger
surface-detector station positions, signal-start times, and timing uncertainties.

## Scientific question

> How accurately can a transparent, uncertainty-aware physical model reconstruct
> an air shower's arrival direction, where does that model fail, and can a
> leakage-safe physical or machine-learning correction improve it?

The project begins with a reproducible plane-front baseline. Curvature, robust
fitting, machine-learning correction, and an interactive application are staged
extensions rather than assumed results.

## Current evidence

| Component | Current status |
|---|---|
| Data provenance | Official source definitions and local download manifests are implemented |
| Coordinate convention | Auger's local axes and sky-arrival convention are documented and cross-checked |
| Plane-front fitter | Production module implemented and tested with exact and noisy synthetic showers |
| Event JSON adapter | In active implementation |
| Example real event | Footprint inspected; direction reconstruction not yet evaluated |
| Fixed 1,000-event pilot | IDs and splits prepared; batch reconstruction not yet run |
| Curved front, robust fit, ML, deployment | Planned research and product stages |

The example event `081847956000` was used to verify field meanings and direction
conventions, so it is an **unblinded integration example**, not a blinded result.

## Scientific boundary

The fitter itself does not receive Auger's released direction, core, curvature,
energy, or fit-quality quantities. The first baseline does, however, use
`stations[].isSelected`, which records Auger's decision about which triggered
stations belong in its reconstruction. It is therefore an independently
implemented fit with **Auger-assisted station selection**. A later ablation will
replace this flag with independent station-quality rules.

For real data, Auger's released direction is an evaluation reference rather than
physical ground truth. Accordingly, real-event performance is reported as angular
separation from the released Auger reference. True angular error is available only
in controlled synthetic experiments.

## Verify the completed core

Install the locked environment and run the completed validation, cohort, and
plane-front tests:

```bash
uv sync
uv run pytest tests/test_validation.py tests/test_cohort.py tests/test_plane_front.py
```

The in-progress event-adapter files are intentionally not included in this command
until their implementation is complete.

## Obtain and inspect the example data

```bash
uv run auger sources
uv run auger download first-event
uv run auger validate data/raw/events/Auger_081847956000.json
uv run auger inspect data/raw/events/Auger_081847956000.json
uv run auger download summary
uv run auger build-pilot
```

Raw data are excluded from Git. Every completed download is recorded in
`data/manifests/downloads.jsonl` with its source URL, observed size, and local
checksums. Published expected size and MD5 values are additionally checked for the
summary and auxiliary archives.

## Repository map

```text
configs/                   Versioned data-source and cohort definitions
data/                      Local data areas and tracked provenance manifests
docs/                      Scientific decisions, field policy, roadmap, and lessons
notebooks/                 Explanatory experiments; reusable logic belongs in src/
reports/figures/           Exploratory and reproducible scientific figures
src/auger_reco/data/       Downloading, parsing, cohort, and validation tools
src/auger_reco/physics/    Geometry and direction-reconstruction models
src/auger_reco/evaluation/ Planned population-level evaluation tools
src/auger_reco/ml/         Planned residual-correction models
tests/                     Deterministic unit and numerical tests
```

See [`docs/scientific_charter.md`](docs/scientific_charter.md) for the claims
boundary, [`docs/field_policy.md`](docs/field_policy.md) for leakage rules, and
[`docs/project_scope_and_deployment.md`](docs/project_scope_and_deployment.md) for
the full staged research and deployment roadmap.

## Authoritative data source

Pierre Auger Open Data, Release 3 (20 March 2024):

- Portal: <https://opendata.auger.org/>
- Dataset DOI: <https://doi.org/10.5281/zenodo.4487612>
- Release DOI: <https://doi.org/10.5281/zenodo.10488964>

This is an independent student project and is not affiliated with or endorsed by
the Pierre Auger Collaboration. Auger data are not redistributed by this
repository and remain subject to their original terms and citation requirements.
