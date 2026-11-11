# Auger Direction Reconstruction

An active undergraduate computational-physics project for reconstructing the
arrival direction of ultra-high-energy cosmic-ray air showers from Pierre Auger
surface-detector station positions, signal-start times, and timing uncertainties.

## Scientific question

> How accurately can a transparent, uncertainty-aware physical model reconstruct
> an air shower's arrival direction, where does that model fail, and can a
> leakage-safe physical or machine-learning correction improve it?

The project begins with a reproducible plane-front baseline and now includes a
tested, core-assisted quadratic-front comparison. Robust fitting, independent
core/selection improvements, machine learning, and an interactive application
remain research/product stages rather than assumed results.

## Current evidence

The [published evidence index](reports/README.md) links the reviewed result
tables and figures included in Git. Full local run archives are preserved but
are not all distributed in this repository; see the
[publication and provenance notes](docs/publication_notes.md).

| Component | Current status |
|---|---|
| Data provenance | Official source definitions and local download manifests are implemented |
| Coordinate convention | Auger's local axes and sky-arrival convention are documented and cross-checked |
| Plane-front fitter | Production module implemented and tested with exact and noisy synthetic showers |
| Event JSON adapter | Implemented, tested, and integrated with real-event fitting |
| Real-event curvature | Plane and published-core-assisted quadratic models compared, retaining failures and station-holdout diagnostics |
| Fixed 1,000-event pilot | All 711 training events executed; 145 validation and 144 test events remain sealed |
| Core/signal modelling | Experimental branch studied; not promoted to the frozen baseline |
| Robust fit, ML, deployment | Planned research and product stages |

The [training-pilot conclusion](reports/training_pilot_conclusion.md) records the
original fits; the [14 October coordinate correction](reports/exported_direction_frame_conclusion.md)
supersedes its reference-angle comparisons. Across 711 training events, timing-weighted
median nominal reduced chi-square changes from **26.97 to 1.53**, and median
separation from Auger's reference changes from **1.077 to 0.255 degrees** after
putting fitted and reference directions in the same coordinate frame.
The quadratic model lowers held-out timing RMS in **452/466** complete event
pairs. These are training-stage, core-assisted comparisons, not true-direction
accuracy measurements or evidence of superiority to Auger's reconstruction.

The example event `081847956000` was used to verify field meanings and direction
conventions, so it is an **unblinded integration example**, not a blinded result.

The existing 10,000 paired Monte Carlo trials repeat timing noise on one fixed
13-station geometry and true direction; they are not 10,000 distinct showers.
The [coordinate audit](docs/conference_coordinate_audit.md) verifies that the
released positions behave as central-site ENU coordinates, while the published
zenith/azimuth behave as core-local ENU angles. The WGS84 transformation was
checked against redundant released fields; this is not absolute pointing calibration.
Use the corrected reference tables, not historical mixed-frame comparisons.

The correction is now automatic in the real-event notebooks and evaluation
pipeline through `data/direction_reference.py`. Published core-local angles are
rotated into the fitted vectors' central-site frame **after predictions are
saved**. New comparison outputs record the transformation version. Legacy
checkpoints cannot silently resume as corrected results; frozen evidence stays
unchanged. See [the integration guide](docs/direction_frame_integration.md).

## Research roadmap

The full [14-stage Phase 1 plan](docs/research_roadmap.md) covers real-event and
batch reconstruction, protected evaluation cohorts, broader simulations, curved
fronts, independent station selection, detector/timing studies, realistic simulation,
ML/neural corrections, uncertainty, final comparisons, and the scientific report.
Each stage has explicit completion evidence and dependencies.

The full [application vision](docs/project_scope_and_deployment.md) remains intact:
event upload/manual entry, physics and ML comparisons, 3D shower replay, a sky view,
educational experiments, and deployment. Under the current plan, application work
follows the full research phase. Early research releases are useful milestones,
not claims that all extended research is already complete.

## Scientific boundary

The plane fitter does not receive Auger's released direction, core, curvature,
energy, or fit-quality quantities. The first baseline does, however, use
`stations[].isSelected`, which records Auger's decision about which triggered
stations belong in its reconstruction. It is therefore an independently
implemented fit with **Auger-assisted station selection**. A later ablation will
replace this flag with independent station-quality rules.

The quadratic real-event baseline additionally receives the published core
position through a separate adapter, so it is explicitly **Auger-core-assisted**.
Both models exclude the published direction from fitting. Station holdout remains
conditional on the full-event official core and station selection.

For real data, Auger's released direction is an evaluation reference rather than
physical ground truth. Accordingly, real-event performance is reported as angular
separation from the released Auger reference. True angular error is available only
when the generating direction is known, as in synthetic/simulated experiments,
and its interpretation depends on the simulation's realism.

## Verify the completed core

Install the locked environment and run the scientific and data-pipeline tests:

```bash
uv sync
uv run pytest -W error
```

## Obtain and inspect the example data

```bash
uv run auger sources
uv run auger download first-event
uv run auger validate data/raw/events/Auger_081847956000.json
uv run auger inspect data/raw/events/Auger_081847956000.json
uv run auger download summary
uv run auger build-pilot
```

Complete raw event files are excluded from Git; explanatory notebooks retain
small displayed subsets. CLI downloads are recorded in
`data/manifests/downloads.jsonl`; experimental batch downloads have per-event
receipts and checksums in their run directories. Published expected size and MD5
values are additionally checked for the summary and auxiliary archives. See the
[training execution protocol](docs/training_pilot_execution.md) for safe resume,
split isolation, reference-access ordering, and independent numerical auditing.

## Repository map

```text
configs/                   Versioned data-source and cohort definitions
data/                      Local data areas and tracked provenance manifests
docs/                      Scientific decisions, field policy, roadmap, and lessons
notebooks/                 Explanatory experiments; reusable logic belongs in src/
reports/figures/           Exploratory and reproducible scientific figures
src/auger_reco/data/       Downloading, parsing, cohort, and validation tools
src/auger_reco/physics/    Geometry and direction-reconstruction models
src/auger_reco/evaluation/ Paired studies, diagnostics, checkpointed pilot execution
src/auger_reco/ml/         Planned residual-correction models
tests/                     Deterministic unit and numerical tests
```

See [`docs/scientific_charter.md`](docs/scientific_charter.md) for the claims
boundary, [`docs/field_policy.md`](docs/field_policy.md) for leakage rules, and
[`docs/research_roadmap.md`](docs/research_roadmap.md) for the canonical 14 research
stages, completion gates, and rough code budgets. The full scope and deployment
feature inventory remain in
[`docs/project_scope_and_deployment.md`](docs/project_scope_and_deployment.md).

## Authoritative data source

Pierre Auger Open Data, Release 3 (20 March 2024):

- Portal: <https://opendata.auger.org/>
- Dataset DOI: <https://doi.org/10.5281/zenodo.4487612>
- Release DOI: <https://doi.org/10.5281/zenodo.10488964>

This is an independent student project and is not affiliated with or endorsed by
the Pierre Auger Collaboration. Auger data are not redistributed by this
repository and remain subject to their original terms and citation requirements.
