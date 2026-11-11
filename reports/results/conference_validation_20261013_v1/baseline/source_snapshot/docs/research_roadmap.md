# Phase 1 research roadmap: 14 stages

Last reviewed: 2026-09-15

This is the canonical execution plan for the full research phase. It incorporates
the original physics-plus-ML programme and the later discussion of shower-front
curvature, coordinate transformations, independent station selection, realistic
simulation, and uncertainty. It does not replace the full application vision in
[project scope and deployment](project_scope_and_deployment.md).

The stage numbers below are the agreed research milestones. The numbered topics
in the scope document are thematic coverage areas, not another execution order.
Early research releases provide useful, honest milestones for applications; they
do not mean that the full research phase is complete. Under the current plan,
full Phase 1 research precedes application development. Any future decision to
overlap the two tracks must be explicit and must not remove research commitments.

## Starting point and evidence boundary

- Exact and noisy synthetic reconstruction, a reusable plane-front fitter, and
  event-adapter work provide the starting foundation. The first real-event
  reconstruction is being finalized, not yet a completed population study.
- The existing 10,000 paired Monte Carlo trials use one fixed 13-station layout
  and one true direction, with repeated timing-noise realizations. They are not
  10,000 different physical showers or a measurement of real-data performance.
- Event `081847956000` is an unblinded development and integration example: its
  official direction has already been inspected. It cannot become a blind test
  by hiding its answer again.
- Tutorial-level local-axis and sky-arrival angle checks have already been done.
  The exact transformation used to export public station coordinates, including
  treatment of Earth curvature, remains a separate documentation question.
- Pilot IDs and splits exist. The current manifest also contains reference
  values; technical target separation is required before population evaluation.
- Curvature, independent-selection, realistic-simulation, and ML improvements are
  research objectives, not established results. Inspirational poster mock-ups
  with hypothetical results are not scientific evidence.

## Scientific rules shared by all stages

1. **Two evaluation tracks:** simulated truth supports angular-accuracy claims
   within that simulation; real Auger directions support reference-agreement
   claims. Do not call an official reconstructed direction ground truth.
2. **Independent inputs:** no official direction, core, curvature radius, energy,
   fit quality, or direction-derived station distance enters an independent
   reconstruction unnoticed. Any assisted comparison is labelled separately.
3. **Selection is part of the method:** using `isSelected` inherits Auger's
   station-association decision. Selection independent of that flag still acts
   on released triggers, not on the complete detector acquisition stream.
4. **Freeze before evaluation:** protect test targets and freeze preprocessing,
   features, quality cuts, model settings, uncertainty calibration, and analysis
   decisions before test evaluation. An opened test set becomes historical.
5. **Report all outcomes:** retain failures, exclusions, abstentions, null results,
   and regressions, not only successful reconstructions or positive improvements.

## Stage 1 — finish and document the first real event

**Status:** in progress; synthetic and reusable-code foundations exist.

Use the real-event notebook to call the event adapter and production fitter.
Keep reconstruction logic in the reusable modules rather than duplicating it.

- Record validated station inputs, selection provenance, configuration, data
  identity, and software version.
- Report propagation and sky vectors, zenith and azimuth, predicted times, raw
  and standardized residuals, fit/geometry/optimizer diagnostics, and warnings.
- Compare the frozen prediction with the released Auger direction using angular
  separation; label this particular event as an unblinded integration result.
- Inspect unselected triggers using timing, uncertainty, signal, saturation,
  traces when available, and spatial context. Distance alone is not a rejection
  explanation, and a plane-front residual alone is not proof of a bad station.
- Predeclare a different event for a reference-hidden demonstration and record
  its prediction before opening its reference.

**Exit evidence:** a clean-run notebook, saved structured results and diagnostic
figures, explicit limitations, and no claims of population accuracy from one event.

## Stage 2 — finalize data and coordinate assumptions

**Status:** axis/angle foundations documented; export details still to resolve.

- Consolidate existing verified local axes, angle conventions, propagation/sky
  signs, time references, and units without repeating completed tutorial work.
- Record the meaning of station `x`, `y`, `z`, `t`, `dt`, and selection flags,
  including what is measured, calibrated, reconstructed, or still uncertain.
- Resolve or explicitly bound the public coordinate frame, origin, height datum,
  and export transformation, including Earth-curvature treatment.
- Keep Earth curvature distinct from shower-front curvature. Do not assume that
  exported times are already flattened, or add a coordinate correction twice.
- Quantify the timing effect of a justified position change on the actual event
  geometry using `delta_t = dot(u, delta_r) / c`.
- Track the Auger Open Data enquiry and the exact evidence supporting each answer.

**Exit evidence:** a sourced convention/assumption record and sensitivity checks.
Unanswered export questions remain explicit; no speculative correction enters
the default pipeline. Work that does not depend on the answer can continue.

## Stage 3 — establish a reliable multi-event pipeline

**Status:** planned; reuse the current adapter and fitter.

- Run a fixed, varied 10–20-event development cohort, outside protected tests.
- Add reproducible batch execution, configuration capture, structured results,
  per-event warnings/failures, and resumable result handling where needed.
- Exercise schema, units, station counts, geometry, optimizer, and serialization
  edge cases; fix failures with focused regression tests.
- Ensure clean-environment runs do not depend on hidden notebook state.

**Exit evidence:** repeatable development-cohort outputs, recorded failure
denominators, and unit/integration tests. This stage does not open the pilot test
targets; Stage 4 is a gate before population-level comparison.

## Stage 4 — protect the pilot and final evaluation cohorts

**Status:** pilot identifiers prepared; target quarantine still required.

- Preserve the frozen 1,000-event pilot and its split history; do not rebuild
  favourable splits after looking at results.
- Generate a target-free execution manifest and a separately controlled reference
  store. Merely promising not to read direction columns is insufficient.
- Audit cohort membership, duplicate physical events, and prior target exposure.
  Use train/development and validation data for debugging and method selection.
- Reserve a non-overlapping final benchmark before broader cohort exploration.
  Predeclare any intermediate release-specific tests; once opened, label them
  historical and never use them as untouched evidence for a later release.
- Group multiple views and repeated realizations of the same physical or
  simulated shower when measuring generalization. Explicitly distinguish a
  same-layout noise experiment from generalization to new showers/geometries.

**Exit evidence:** versioned manifests, split/exposure audit, enforceable feature
and reference separation, and a written evaluation protocol. No test-dependent
feature, exclusion, or model selection is allowed.

## Stage 5 — establish the physics comparison framework

**Status:** constrained-fit and synthetic comparison foundations exist.

Establish consistent inputs, outputs, metrics, timing, and failure accounting for:

1. uniform and timing-weighted linear plane fits;
2. normalized linear estimates, labelled as estimates rather than constrained optima;
3. uniform and timing-weighted unit-vector-constrained plane fits;
4. robust fits, curvature-aware fits, and independent station selection;
5. physics-plus-ML variants introduced later.

**Exit evidence:** tested available baselines and a common comparison harness.
Stages 7–11 populate the later entries; Stage 5 does not require those methods to
exist already. Ablations distinguish weighting, constraints, loss, selection,
curvature, and learning rather than changing everything simultaneously.

## Stage 6 — expand controlled shower simulations

**Status:** planned beyond the completed fixed-geometry noise experiment.

- Vary true zenith/azimuth, station geometry, multiplicity, elevations, and
  near-flat or ill-conditioned layouts; include valid and expected-failure cases.
- Introduce controlled curvature, missing stations, timing outliers, offsets,
  uncertainty miscalibration, non-Gaussian noise, and correlated timing errors.
- First isolate one effect at a time, then test predeclared combinations.
- Pair methods on identical generated measurements and retain seeds, true
  parameters, simulator settings, and all reconstruction outcomes.
- Separate training, validation, and final simulation tests at an appropriate
  shower/scenario level; avoid leaking near-identical realizations across splits.

**Exit evidence:** reusable generation and experiment tools, recovery/robustness
tests, and truth-based accuracy plots across conditions. These are controlled
toy-model results until detector realism is established in Stage 10.

## Stage 7 — develop curvature-aware reconstruction

**Status:** planned.

- Compare plane, spherical, and quadratic/paraboloidal front approximations.
- Define the shower-axis/core location, curvature parameters, constraints,
  initialization, and identifiability assumptions for each model.
- Estimate required quantities independently where possible. Any experiment
  using Auger's reconstructed core or radius is a separately labelled assisted
  comparison, not the independent primary method.
- Test parameter degeneracy, sensitivity to starting values, geometry, station
  count, and noise using the Stage 6 simulator before real-data interpretation.

**Exit evidence:** tested curved-front models and paired accuracy/reference
comparisons. Lower timing residuals alone do not demonstrate improved direction
accuracy; account for extra flexibility and report failures and regressions.

## Stage 8 — investigate station selection and robust fitting

**Status:** planned; assisted `isSelected` baseline remains available.

- Study measurement-quality rules, robust residual weighting, timing-compatible
  station association, and guarded iterative selection/refitting.
- Compare selection rules separately from robust loss choices and front models.
  Do not automatically discard distant stations or legitimate curved-front delays.
- Compare independently selected released triggers with the assisted baseline;
  report retention, contamination in simulations, angular performance, and
  reconstruction failures rather than only agreement with `isSelected`.
- Investigate a learned station-quality model later only with valid targets and
  leakage-safe evaluation. Its decision must remain inspectable.

**Exit evidence:** reproducible selection/robustness ablations and documented
limitations of working with released rather than all detector triggers.

## Stage 9 — investigate timing and detector effects

**Status:** planned, guided by residual evidence.

- Examine dependence on `dt`, signal and signal uncertainty, saturation,
  multiplicity, station geometry, and available PMT-trace features.
- Test uncertainty calibration, correlated errors, common timing offsets, and
  physically motivated timing corrections under controlled conditions.
- Investigate weather or auxiliary metadata only where availability, timing
  alignment, and a physical rationale support an experiment.
- Distinguish a diagnostic correlation from a justified corrective model.

**Exit evidence:** evidence-backed detector/timing studies and validated
corrections or documented null/negative findings. Missing metadata is recorded
as a limitation, not imputed from official reconstruction outputs.

## Stage 10 — realistic simulation and a fair Auger comparison

**Status:** access-dependent; no suitable ready-to-use paired sample verified.

- Seek samples with generated true direction plus detector-level station
  positions, times, uncertainties, selection/trigger information, and provenance.
  True direction alone is a target, not sufficient input to test reconstruction.
- Distinguish toy fronts, particle-level air-shower simulation with an explicit
  detector approximation, and validated detector-level simulation.
- Explore an established shower-simulation workflow such as CORSIKA only with
  explicit detector-response assumptions and a feasible access/computing plan.
- A direct truth-accuracy comparison with official Auger reconstruction requires
  comparable reconstructions on the same simulated events and transparent input
  information budgets. Our toy simulator alone cannot establish superiority.
- Document simulator versions, calibration/domain limits, and simulation-to-data
  differences; use independent references only with their uncertainties stated.

**Exit evidence:** a provenance-documented realistic validation and, if the
necessary official comparison data are obtained, a fair matched comparison.
Unavailable promised data leave this stage access-limited; they do not count as
a completed study. Building a complete detector simulator from scratch is not
silently included in the code budget or current implementation commitment.

## Stage 11 — develop and evaluate ML and neural corrections

**Status:** planned after reliable physical baselines and data controls.

- Compare regularized linear correction, tree models, compact neural models, and
  an extended permutation-invariant station-set or graph-model experiment.
- Study small tangent-plane direction corrections, corrected unit vectors,
  station reliability, and event-level error/reliability estimates.
- Use independently computed geometry, timing, signals, residuals, and fit
  diagnostics; audit every feature and target against the field policy.
- Tune exclusively on training/validation data and compare against the strongest
  justified physics baseline, not only the weakest plane fit.
- Ablate feature groups, model capacity, training targets, and physics components;
  handle variable station counts and station ordering explicitly.
- Label Auger-target training as reference agreement/emulation; use simulation
  truth for truth-accuracy claims, conditional on the simulation model.

**Exit evidence:** reproducible training/inference, model artifacts, leakage audit,
paired comparisons, and documented gains or null/negative results. Neural-network
improvement is a hypothesis to test, not a prerequisite for scientific completion.

## Stage 12 — calibrate uncertainty and reliability

**Status:** planned.

- Estimate directional uncertainty regions and assess calibration and coverage.
- Study bias and coverage versus direction, geometry, multiplicity, noise,
  selection, and distribution shift.
- Define warnings, out-of-domain detection, and abstention rules using only
  development/validation data; report accuracy alongside retained coverage.
- Test physical coverage using known simulated truth. On real data without
  independent truth, describe coverage as reference-relative.
- Interpret chi-square with the actual error model and fitting procedure;
  nonlinear constraints, robust losses, correlations, or data-dependent station
  rejection can invalidate a naive reduced-chi-square interpretation.

**Exit evidence:** calibrated uncertainty/reliability outputs, coverage plots,
subgroup diagnostics, and a documented failure/abstention policy.

## Stage 13 — freeze and run the comprehensive final comparison

**Status:** planned; requires protected data from Stage 4.

- Freeze code, configuration, features, preprocessing, selection, exclusions,
  metrics, model choices, and statistical procedures before opening final tests.
- Compare all evaluated baselines and improvements on the same permitted inputs
  and event sets; include component and feature ablations.
- Report median, 68th/95th-percentile angular error or reference separation,
  paired per-event differences and appropriate confidence intervals, runtime,
  uncertainty coverage, failures, exclusions, and abstentions.
- Use event/shower-level uncertainty resampling consistent with grouping; report
  accuracy on common successful events alongside full eligible denominators.
- Stratify outcomes and regressions by justified conditions. Expand to a larger
  cohort only under the frozen protocol; treat SD-750 and inclined events as
  separate distribution-shift studies, not automatically validated inputs.

**Exit evidence:** one-time final benchmark results, reproducible figures/tables,
and explicit limits on what generalizes. Later changes require a new evaluation
plan rather than reuse of the opened test as untouched evidence.

## Stage 14 — complete the scientific package and review

**Status:** planned; learning notes and existing tests are foundations.

- Deliver tested source, environment lock/configuration, provenance and split
  manifests, experiment records, model artifacts, and regeneration instructions.
- Write a concise report plus a technical methods/limitations report, including
  literature context, negative results, novelty boundaries, and failure cases.
- Complete data/feature documentation and a model card for learned methods.
- Prepare a small physics/residual review package for Michel's offered sanity
  check; incorporate feedback without implying formal endorsement or authorship.
- Update the conference poster/abstract claims to match actual completed work.
  Clearly distinguish hypothetical design assets from research figures.
- Verify the released study from a clean environment and archive a versioned
  research release before moving to the application stage.

**Exit evidence:** a reproducible full-scope research package and a record of
review/remaining limitations. Publication acceptance, a positive ML result, and
outperforming Auger are not completion requirements.

## Dependencies and completion gates

- **Immediate path:** Stage 1 -> remaining Stage 2 assumptions -> Stage 3
  development runs -> Stage 4 evaluation safeguards -> Stage 5 comparisons.
  Export enquiries can run alongside safe work, but unresolved assumptions must
  not be hidden in final scientific claims.
- **Experimental path:** Stage 6 supports Stages 7–9; the Stage 10 data enquiry
  starts early because access is external. Stage 11 builds on validated physics,
  and Stage 12 is evaluated alongside every mature candidate method.
- **Release path:** Stage 13 follows the final procedure freeze; Stage 14 packages
  the results and closes the research phase. Readiness for an early report is
  distinct from readiness to declare all of Phase 1 complete.
- **No silent scope cuts:** an unavailable dataset or unperformed promised study
  stays planned/access-limited unless a scope change is explicitly agreed and
  documented. Record scientifically justified decisions not to retain a tested
  method; do not require every experiment to yield an improvement.
- **Deployment handoff:** use only validated model capabilities and uncertainty
  claims in the app. Preserve all planned upload, manual-entry, replay, 3D sky,
  comparison, education, reporting, and cloud features in the product scope.

## Rough additional code budget

These are planning ranges, not progress percentages, quality targets, deadlines,
or an instruction to type everything by hand. Reuse the existing adapter, fitter,
tests, and notebook logic. Count additional core code separately from tests and
analysis code; exclude prose, generated notebook JSON, data, third-party code,
already-written source, and the entire application/deployment phase.

| Stage | Additional core lines | Tests and analysis lines | Total additional lines |
|---|---:|---:|---:|
| 1. First real event | 25–100 | 100–250 | 125–350 |
| 2. Data and coordinates | 100–250 | 100–250 | 200–500 |
| 3. Multi-event pipeline | 100–200 | 75–150 | 175–350 |
| 4. Protected cohorts | 150–300 | 100–250 | 250–550 |
| 5. Baseline framework | 150–300 | 150–300 | 300–600 |
| 6. Controlled simulations | 250–500 | 200–400 | 450–900 |
| 7. Curved fronts | 350–700 | 250–500 | 600–1,200 |
| 8. Selection and robust fits | 200–400 | 150–300 | 350–700 |
| 9. Detector and timing studies | 250–600 | 200–450 | 450–1,050 |
| 10. Realistic simulation integration | 250–600 | 150–400 | 400–1,000 |
| 11. ML and neural corrections | 600–1,200 | 400–800 | 1,000–2,000 |
| 12. Uncertainty and reliability | 300–600 | 250–500 | 550–1,100 |
| 13. Final comparisons | 250–500 | 300–600 | 550–1,100 |
| 14. Reproducible research package | 150–300 | 100–200 | 250–500 |
| **Total** | **3,125–6,550** | **2,525–5,350** | **5,650–11,900** |

Roughly 6,000–12,000 additional lines is an implementation estimate under these
assumptions, not a ceiling on scientific scope. Detector studies, realistic-data
integration, and ML are the most uncertain parts. The estimate assumes reuse of
established simulation and learning tools; a new full detector simulator would
require a separate feasibility and resource plan.
