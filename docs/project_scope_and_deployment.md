# Full project scope and staged roadmap

Last reviewed: 2026-08-30

## Purpose of this document

This document preserves the complete ambition of the Auger direction-reconstruction
project across both phases:

1. **Phase 1 — computational-physics research:** independently reconstruct cosmic-ray
   air-shower arrival directions, diagnose the limitations of transparent physical
   baselines, and develop validated physical and machine-learning improvements.
2. **Phase 2 — software product and deployment:** turn the tested research pipeline
   into an interactive, educational, scientifically responsible web application.

The project scope is not reduced when deadlines approach. Work is ordered into
milestones so that each research release produces an independently defensible result,
while later improvements remain visible as active development.

| Area | Current milestone |
|---|---|
| Research | Research Release 0 substantially complete; Release 1 in progress |
| Deployment | Planned after the first defensible end-to-end research result |

## Project thesis

The central research question is:

> How accurately can an independent, uncertainty-aware reconstruction recover the
> arrival direction of a cosmic-ray air shower from Pierre Auger surface-detector
> station positions and timing measurements, and can physically motivated or
> machine-learning corrections improve that reconstruction on predeclared held-out
> events whose evaluation targets are technically quarantined during development?

The project is deliberately hybrid:

- physics supplies the geometry, timing equation, constraints, diagnostics, and
  interpretable baselines;
- statistics supplies uncertainty-aware fitting, validation, calibration, and
  honest comparisons;
- machine learning targets residual structure that remains after the physical model;
- software engineering makes the scientific pipeline reusable, testable, and
  accessible through an interactive application.

## Scientific claims boundary

The project may claim improvement over its own independently implemented baselines
when the appropriate target-quarantined test cohort supports that conclusion. It must not
automatically claim
to outperform the Pierre Auger Collaboration's official reconstruction because:

- the released Auger direction is a reference reconstruction, not absolute truth;
- the official pipeline uses calibration and detector knowledge beyond the simplified
  public reconstruction developed here;
- training toward the released direction and then claiming superiority over that same
  direction would be circular.

Real-data claims will therefore use language such as:

- "reduced angular separation to the released Auger reference relative to our
  independent plane-front baseline";
- "improved robustness or uncertainty calibration on held-out events";
- "outperformed a simplified physical baseline under known synthetic truth."

Stronger claims require an independent truth source, such as controlled simulations
or a justified higher-precision comparison sample. Investigating suitable hybrid or
simulation-based references remains part of the full research scope.

# Phase 1 — full research scope

## 1. Data provenance and reproducibility

- Use the official Pierre Auger Open Data release as the authoritative source.
- Record source URLs, release identifiers, sizes, and checksums.
- Preserve raw data outside Git and track deterministic manifests.
- Deduplicate physical events that appear through multiple reconstruction views.
- Freeze train, validation, and test event identifiers before modelling.
- Preserve a separate fixed evaluation cohort for each declared research release and
  technically withhold its reference directions while models are being developed.
  Once its result is viewed, that cohort becomes a historical benchmark and must not
  be described as untouched or used to select later improvements.
- Before opening a release's test cohort, freeze all preprocessing, feature,
  model-selection, metric, exclusion, and statistical-analysis decisions for that
  release.
- Reserve a non-overlapping final benchmark for the completed full-scope study.
- Record all cohort rules, exclusions, failures, and software environments.
- The current pilot manifest contains both split assignments and released reference
  values. Before batch evaluation, generate a label-free execution manifest and load
  reference values only after predictions for that release are frozen.

## 2. Data understanding and leakage control

- Validate the meaning and units of `x`, `y`, `z`, `t`, `dt`, signal, selection,
  saturation, and PMT-trace fields.
- Distinguish calibrated pseudo-raw measurements from official reconstruction outputs.
- Quarantine official direction, core, curvature, energy, fit-quality, and
  direction-derived fields from baseline inputs.
- Treat official zenith and azimuth as evaluation references only.
- Separate model features, diagnostic metadata, and evaluation-only information.
- Audit every future feature for direct, indirect, and split-level leakage.
- Treat `isSelected` as an Auger-reconstruction-assisted input, not an independent raw
  measurement. Preserve an assisted baseline for comparison, but require an ablation
  without `isSelected` and develop independent station-quality rules for stronger
  independence claims.

## 3. Physics and mathematical foundations

- Derive the moving plane-front equation from plane geometry.
- Distinguish the downward propagation vector from the upward sky-arrival vector.
- Verify the Auger coordinate, zenith, and azimuth conventions.
- Derive ordinary and timing-uncertainty-weighted least squares.
- Use centred coordinates and times for numerical stability.
- Solve linear systems with QR/SVD-style least-squares solvers rather than explicit
  matrix inversion.
- Enforce the unit-vector and downward-propagation constraints.
- Convert fitted vectors into zenith and azimuth safely with `atan2` and clipping.
- Evaluate directions with three-dimensional angular separation.
- Derive residual, standardized-residual, chi-square, reduced-chi-square, rank, and
  conditioning diagnostics.

## 4. Synthetic validation program

- Recover an exact shower with effectively zero angular and timing error.
- Add independent Gaussian timing errors consistent with each station's `dt`.
- Compare weighted and unweighted fits through paired Monte Carlo trials.
- Test all four azimuth quadrants.
- Test nearly vertical and high-zenith showers.
- Test different station multiplicities and geometries.
- Test unequal elevations and nearly flat arrays.
- Detect rank-deficient and poorly conditioned layouts.
- Test zero, negative, missing, infinite, and invalid uncertainties.
- Test timing outliers and controlled systematic offsets.
- Test model behavior under known shower-front curvature.
- Record expected failures rather than silently coercing them into predictions.

## 5. Reusable reconstruction software

- Move validated notebook logic into `src/auger_reco/physics/`.
- Use explicit units, validated schemas, focused functions, and structured result
  objects.
- Keep notebooks as explanatory experiments rather than authoritative implementations.
- Produce predicted times, direction vectors, angles, residuals, fit quality,
  conditioning diagnostics, and failure status.
- Add deterministic unit, integration, and regression tests.
- Provide batch reconstruction without hidden notebook state.
- Preserve model and software version provenance with every result.

## 6. Reference-hidden real-event reconstruction

- Use event `081847956000` as an unblinded integration and convention check because
  its released answer was already inspected during the tutorial audit.
- Predeclare a different real event for a genuinely reference-hidden demonstration.
- Record the predicted direction before revealing the reference.
- Compare using angular separation only after the prediction is frozen.
- Plot measured and predicted station times.
- Map raw and standardized residuals across the array.
- Inspect the influence of uncertainty, signal, selection, saturation, and geometry.
- Document every sign, unit, convention, or data-quality failure encountered.

## 7. Multi-event reconstruction cohorts

- Begin with a varied 10–20-event smoke-test cohort.
- Repair parser, geometry, optimizer, and diagnostic failures.
- Run the stable pipeline on the frozen 1,000-event pilot.
- Expand to a larger justified subset or the complete appropriate release when useful.
- Report success and failure rates rather than analysing only successful events.
- Stratify performance by zenith, azimuth, multiplicity, energy, detector array,
  timing uncertainty, signal, saturation, and geometry quality.

## 8. Transparent baselines and ablations

The project will preserve and compare at least:

1. unweighted linear plane-front reconstruction;
2. timing-uncertainty-weighted linear reconstruction;
3. normalized linear direction estimate;
4. physically constrained weighted plane-front reconstruction using Auger's station
   selection as an explicitly labelled assisted baseline;
5. robust timing fit that reduces sensitivity to outliers;
6. physically motivated curved-front reconstruction;
7. an independently cleaned reconstruction that does not use `isSelected`;
8. physics baseline plus machine-learning residual correction.

Every comparison should change one important methodological choice at a time when
possible. Ablations must distinguish gains caused by weighting, constraints, robust
losses, curvature, feature groups, and ML capacity.

## 9. Physical and statistical improvements

Candidate improvements remain in scope and will be prioritized using real residual
evidence:

- explicit shower-front curvature;
- robust losses or station-level outlier handling;
- empirical checking and calibration of `dt`;
- geometry-aware event-quality indicators;
- uncertainty-aware station selection;
- independent station-cleaning rules compared with `isSelected`;
- correlated-error or event-level systematic models when supported by evidence;
- improved initialization and multi-start optimization for difficult events.

A correction is retained only if it improves held-out behavior or provides a useful,
honestly reported robustness result. A null result remains scientifically valid.

## 10. Machine-learning research program

ML will augment rather than replace the physical reconstruction. Candidate targets
include:

- a small two-dimensional correction in the tangent plane around the baseline
  direction;
- a corrected unit sky vector;
- event-level expected angular error;
- calibrated confidence or an abstention decision;
- station-level influence or outlier probability.

When trained against released Auger directions, the ML model learns to reduce
disagreement with that reference reconstruction; this alone does not establish a
closer estimate of the unknown true direction. Improvement in physical accuracy can
be established directly on controlled synthetic or simulated events with known truth.
Real-data claims remain reference-agreement claims unless an independent truth source
is introduced.

Candidate feature groups include:

- baseline direction and fit diagnostics;
- spatial patterns of raw and standardized timing residuals;
- station coordinates expressed relative to a fitted reference point;
- timing uncertainties;
- signal and signal uncertainty;
- multiplicity and saturation summaries;
- geometry rank, singular values, baselines, and conditioning;
- physically justified curvature or distance summaries calculated independently of
  the official reconstruction.

The modelling ladder will begin with simple, auditable methods and expand only when
validation supports additional complexity:

1. regularized linear correction;
2. tree-based nonlinear models;
3. compact neural models when justified;
4. permutation-invariant station-set or graph-based models as an extended objective.

Model selection will use training and validation data only. Each release-specific
test cohort is opened once after that release's full procedure is frozen. No opened
cohort can be reused as untouched evidence for a later release. GPU availability is
an engineering resource, not a justification for unnecessary model complexity.

## 11. Uncertainty, reliability, and failure-aware output

- Estimate event-level angular uncertainty or containment. On real events evaluated
  only against Auger's released direction, label this as **reference-relative angular
  uncertainty or containment**, not uncertainty relative to unknown physical truth.
- Use synthetic or simulated truth, or a justified independent reference, for direct
  physical-coverage claims.
- Test calibration: events assigned higher confidence should actually be more
  accurate.
- Define an abstention or review policy for unreliable events.
- Measure coverage, selective accuracy, and failure rate.
- Preserve explicit warnings for invalid geometry, optimizer failure, extrapolation,
  and out-of-distribution inputs.
- Compare uncertainty behavior across event subgroups.

## 12. Final evaluation

Primary metrics include:

- median angular separation;
- 68th-percentile angular separation;
- 95th-percentile angular separation;
- paired per-event differences between methods;
- reconstruction and abstention failure rates;
- subgroup performance;
- uncertainty calibration and coverage;
- bootstrap confidence intervals where appropriate.

Final reporting must include both improvements and regressions, representative events,
worst cases, and limitations. Statistical significance and practical effect size must
not be confused.

## 13. Research artifacts

- reproducible source code and tests;
- frozen cohort and experiment manifests;
- learning and derivation notes;
- validated notebooks;
- final scientific figures and tables;
- a concise research report;
- an extended technical report or preprint-style document;
- a model card and data/feature documentation;
- a short mentor-review package containing the question, methods, strongest figure,
  limitations, and reproducibility instructions.

# Staged research releases

These releases prioritize work without deleting any part of the full scope.

## Research Release 0 — foundations

Status: substantially complete.

- repository, data strategy, and leakage policy;
- official tutorial audit;
- coordinate and direction convention verification;
- mathematical learning modules;
- first-event data exploration;
- exact synthetic reconstruction.

## Research Release 1 — application-ready core result

Target: the first defensible end-to-end research result.

- noisy synthetic validation;
- reusable tested fitter;
- unblinded first-event integration check and a separate predeclared,
  reference-hidden demonstration event;
- frozen pilot evaluation;
- baseline comparisons;
- one physical improvement;
- one leakage-safe ML residual correction;
- one-time comparison on the target-quarantined Research Release 1 test cohort;
- concise report and reproducibility instructions.

Completion permits the accurate statement:

> An initial end-to-end research study is complete; extended physical modelling,
> uncertainty calibration, and interactive deployment remain in active development.

## Research Release 2 — physical robustness

- expanded real-event cohort;
- curved-front and robust-fitting ablations;
- independent station cleaning;
- deeper failure and subgroup analysis;
- uncertainty calibration and abstention;
- systematic checks involving weather or other justified metadata.
- one-time evaluation on the target-quarantined Research Release 2 test cohort.

## Research Release 3 — advanced ML and full research package

- extended feature and model ablations;
- station-set or graph model if justified;
- simulation or independent-reference investigation;
- one-time evaluation on the reserved, non-overlapping final benchmark;
- optional full-cohort descriptive analysis after the primary result, clearly labelled
  as post-evaluation rather than untouched evidence;
- expanded report, model card, and mentor-review artifacts.

# Phase 2 — interactive application and deployment

## Product vision

The provisional product name is **ShowerScope**: an interactive cosmic-ray
air-shower reconstruction laboratory that allows a user to upload, enter, replay,
fit, compare, and understand a detector event.

The product should serve:

- students learning air-shower geometry;
- researchers or instructors exploring reconstruction behavior;
- recruiters and technical reviewers evaluating the project;
- curious public users interacting with authentic cosmic-ray measurements.

## Scientifically accurate visual story

The animation will:

1. display the detector array and every triggered station;
2. advance through the event in nanoseconds;
3. illuminate each station when its signal begins;
4. animate one tilted shower front sweeping through the array;
5. show how station timing determines the fitted propagation vector;
6. reverse that vector to show the reconstructed sky-arrival direction;
7. draw an uncertainty cone rather than an unjustified exact point;
8. compare physics-only, physically improved, and ML-assisted directions.

The moving surface is an **effective fitted equal-arrival-time front**. It represents
the collective timing structure of many secondary shower particles; it is not a
material sheet that passes through one detector tank and then continues into the
next. The interface and teaching mode must make that distinction explicit.

The interface must describe the result as the reconstructed arrival direction at
Earth. It must not automatically identify an astrophysical source because charged
cosmic rays can be deflected by magnetic fields during propagation.

## Input modes

### Built-in demonstrations

- curated Auger example events;
- exact and noisy synthetic showers;
- intentionally difficult or failed events;
- guided examples demonstrating weighting, curvature, and outliers.

### File upload

- Auger-style event JSON;
- a documented canonical JSON schema;
- station-per-row CSV;
- optional PMT traces and event metadata.

### Manual station editor

Users can add, remove, and edit stations with required fields:

```text
station_id, x, y, z, t, dt
```

Optional fields include:

```text
signal, dsignal, isSelected, sat, pmt1, pmt2, pmt3
```

The editor will make units explicit and validate changes immediately.

Every uploaded or manually created event must also declare, select, or safely infer:

- coordinate frame and axis orientation;
- position and time units;
- azimuth origin and clockwise/counter-clockwise convention;
- whether a supplied direction is a propagation or sky-arrival vector;
- whether station times are absolute or relative and what their reference means.

If these conventions cannot be resolved unambiguously, validation must stop rather
than return a plausible-looking but sign- or convention-inverted direction.

## Validation experience

Before fitting, the application checks:

- schema and required fields;
- finite numerical values;
- positive timing uncertainties;
- duplicate station identifiers;
- minimum station count;
- coordinate and timing units;
- geometry rank and conditioning;
- implausible timing ranges;
- model compatibility and out-of-distribution warnings;
- file-size and upload limits.

Errors should identify the exact station and field rather than returning a generic
failure.

## Reconstruction output

- fitted propagation and sky-arrival vectors;
- zenith and azimuth;
- event-level angular uncertainty or containment cone;
- predicted station times;
- raw and standardized residuals;
- chi-square and reduced chi-square;
- rank and geometry-conditioning diagnostics;
- model/version provenance;
- reliability, abstention, and warning status;
- comparison with an official reference when the user explicitly supplies one.

## Interactive features

### Event replay

- play, pause, restart, and scrub through nanoseconds;
- adjustable playback speed;
- station illumination synchronized with measured time;
- simultaneous display of the fitted front.

### Three-dimensional detector view

- orbit, pan, and zoom around the array;
- optional terrain/elevation exaggeration;
- station marker size based on signal;
- colour based on time or residual;
- selected and rejected stations shown distinctly.

### Sky-direction view

- local sky dome with compass and zenith reference;
- physics, physical-correction, ML, and reference directions;
- uncertainty cones and angular separations;
- optional celestial-coordinate view when timestamp and site information permit it.

### Station inspector

Clicking a station reveals:

- position, timing, uncertainty, and signal;
- predicted time and residual;
- standardized residual and fit influence;
- selection and saturation status;
- PMT traces when available.

### What-if laboratory

Users can:

- remove or restore a station;
- change its uncertainty;
- perturb its time;
- drag a synthetic station position;
- introduce an outlier;
- compare weighted and unweighted results;
- switch curvature, robust fitting, and ML correction on or off;
- watch the direction and confidence update.

### Blind reconstruction challenge

- hide the reference direction for a public event;
- let the user inspect and reconstruct it;
- reveal the reference afterward;
- report angular separation and explain the main residual patterns.

### Explain-this-result mode

The application explains:

- how timing establishes direction;
- why a station received more or less weight;
- what a positive or negative residual means;
- why the model considers an event reliable or unreliable;
- how the physical and ML predictions differ;
- which limitations prevent a stronger claim.

### Comparison and reporting

- side-by-side method comparison;
- downloadable results JSON or CSV;
- downloadable event report;
- shareable event configuration when privacy and storage design permit it;
- reproducible command or API request corresponding to the interactive run.

## Application architecture

```text
Next.js + TypeScript web interface
    |
    |-- upload and manual station editor
    |-- tables, plots, education, and experiment controls
    `-- React Three Fiber / Three.js event and sky animation
                    |
                    | validated HTTP request
                    v
Python FastAPI reconstruction service
    |
    |-- schema and unit validation
    |-- physics and robust reconstruction
    |-- ML inference and uncertainty calibration
    |-- diagnostics and provenance
    `-- downloadable result generation
                    |
                    v
Versioned model artifacts, schemas, examples, and experiment metadata
```

Python remains authoritative for scientific inference. TypeScript controls the user
experience and browser animation. The browser animates returned measurements and
vectors; it does not independently reimplement the scientific fit.

## Proposed API surface

- `POST /validate` — validate an uploaded or manually entered event;
- `POST /reconstruct` — run selected physics and ML methods;
- `POST /compare` — compare multiple reconstruction configurations;
- `GET /examples` — list curated demonstration events;
- `GET /models` — list available model versions and capabilities;
- `GET /health` — deployment health check;
- `GET /schema` — return the canonical input and output schemas.

The final API contract will be versioned before frontend development so the
scientific backend and interactive client can evolve independently.

## Reproducibility and operational requirements

- Docker images for frontend and backend;
- a local multi-service development configuration;
- locked Python and JavaScript dependencies;
- API, unit, integration, and browser tests;
- continuous integration for linting, tests, and container builds;
- structured logging without leaking uploaded content;
- model and schema versioning;
- request size, timeout, and resource limits;
- safe parsing of untrusted JSON and CSV uploads;
- clear retention and deletion policy if uploads are ever stored;
- accessibility, keyboard controls, responsive layout, and reduced-motion mode;
- public scientific limitations and data attribution.

## Deployment build order

The order below prioritizes working vertical slices without removing later features.

### Deployment Release 0 — scientific API

- canonical input/output schema;
- validation endpoint;
- physics and ML reconstruction endpoint;
- automatic API documentation;
- deterministic example requests;
- backend container and tests.

### Deployment Release 1 — usable web interface

- file upload;
- manual station table;
- validation feedback;
- reconstruction controls;
- numerical results and two-dimensional diagnostic plots.

### Deployment Release 2 — interactive scientific visualization

- three-dimensional detector view;
- nanosecond event replay;
- moving shower front;
- sky dome, method vectors, and uncertainty cones;
- station inspector.

### Deployment Release 3 — educational and experimental laboratory

- what-if controls;
- blind reconstruction challenge;
- explain-this-result mode;
- curated event stories;
- downloadable and shareable reports.

### Deployment Release 4 — production cloud release

- frontend and backend containers;
- cloud deployment, HTTPS, monitoring, and restart policy;
- performance, security, accessibility, and browser testing;
- public documentation and demonstration video.

## Extended product objectives

- batch upload and cohort dashboards;
- compare model versions over saved events;
- user-created synthetic arrays and showers;
- educational lessons connected to interactive controls;
- optional magnetic-deflection exploration clearly labelled as model-dependent;
- multilingual explanations;
- instructor mode and classroom exercises;
- public benchmark leaderboard only if submissions and ground truth can be governed
  scientifically and securely.

# Application and portfolio reporting

Applications should report completed milestones precisely while retaining the full
roadmap. Suitable status language evolves as follows:

| Project state | Accurate description |
|---|---|
| Foundations and synthetic work | Independent computational-physics research in progress; exact/noisy synthetic direction validation completed or underway |
| Research Release 1 complete | Initial end-to-end research study completed on held-out Auger Open Data; extended physical and ML robustness work active |
| Deployment Release 0–1 | Validated research pipeline exposed through a containerized API and interactive upload interface |
| Deployment Release 2+ | Interactive 3D shower replay and physics-versus-ML reconstruction platform in active development or released |

Future work should be described as planned or active, never as completed before the
corresponding artifact exists.

# Full definition of done

## Phase 1 research is fully complete when

- all promised baseline, physical, ML, uncertainty, and robustness studies are either
  completed or explicitly closed with a documented reason;
- the final non-overlapping benchmark evaluation is frozen and reproducible;
- failures and limitations are reported alongside successes;
- source code, tests, manifests, figures, and reports can be regenerated from a clean
  environment;
- project claims follow the scientific boundary in this document.

## Phase 2 deployment is fully complete when

- users can submit a valid event through built-in, uploaded, or manual input;
- the application returns versioned physics and ML reconstructions with diagnostics;
- the event can be replayed accurately in three dimensions;
- results, uncertainty, warnings, and scientific limitations are understandable;
- containers, automated tests, security controls, documentation, and a public cloud
  deployment are operational.

# Technical references for Phase 2

- [Next.js deployment options](https://nextjs.org/docs/app/getting-started/deploying)
- [React Three Fiber: first scene](https://r3f.docs.pmnd.rs/getting-started/your-first-scene)
- [FastAPI deployment](https://fastapi.tiangolo.com/deployment/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
