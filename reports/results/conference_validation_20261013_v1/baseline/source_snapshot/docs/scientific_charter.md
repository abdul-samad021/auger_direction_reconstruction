# Scientific charter

Last reviewed: 2026-09-15

Execution and completion criteria are defined in the
[14-stage research roadmap](research_roadmap.md). The
[full project scope](project_scope_and_deployment.md) preserves research and
application ambitions; this charter defines the scientific claims boundary.

## Primary question

How accurately can independently implemented, uncertainty-aware methods recover
air-shower directions from surface-detector positions, times, and uncertainties,
and how do curvature, station selection, detector effects, and learned corrections
change accuracy, robustness, and reliability?

## Two complementary evaluation tracks

1. **Known simulated truth:** measure true angular error under specified generation
   and detector assumptions. Progress from controlled fronts to realistic
   detector-level validation when the necessary data are available.
2. **Real Auger events:** measure angular separation from the released SD direction.
   This is agreement with an authoritative reconstruction, not a direct measurement
   of error relative to the unknown physical truth.

The research tests physical improvements first and asks whether a leakage-safe ML
or neural correction adds measurable value over the strongest justified physics
baseline. Learning Auger's labels alone does not demonstrate superiority to Auger.

## Primary results

Report median, 68th-percentile, and 95th-percentile angular error or reference
separation, paired method differences with appropriate confidence intervals,
uncertainty calibration, runtime, and failures/exclusions/abstentions. Show paired
accuracy on common successful events alongside the full eligible denominator.
Do not combine simulation-truth and real-reference metrics as interchangeable.

## Baselines and ablations

1. Uniform and timing-weighted linear plane-front fits and normalized estimates.
2. Uniform and timing-weighted unit-vector-constrained fits.
3. Robust timing losses and independent station-selection rules, tested separately.
4. Spherical and quadratic/paraboloidal curvature models with identifiable,
   explicitly constrained parameters and independently derived inputs.
5. Physics-plus-ML corrections: simple regularized models, trees, compact neural
   networks, and an extended station-set/graph-model study.

Study geometry, direction, multiplicity, timing precision, outliers, missing
stations, saturation, and justified detector/auxiliary effects. Official energy
and other reconstructed metadata may support declared evaluation stratification,
not secretly become independent reconstruction inputs. Treat additional arrays
and inclined events as separate domain-shift tests.

## Honest scope

- The public data are a quality-selected 10% release, not the raw detector stream.
- Station start time `t` is a calibrated estimate derived from PMT traces.
- Do not assume `t` is already flattened for shower-front curvature.
- Auger's direction is a reference reconstruction, not absolute ground truth.
- Initially relying on `isSelected` uses Auger's event-association decision; a
  dedicated extension compares independent selection among the released triggers.
- Official direction, core, curvature, energy, fit quality, and direction-derived
  station quantities are quarantined from independent reconstruction features.
- Local-axis and angle checks are documented; the precise public-coordinate
  export transformation remains a separate question. Do not double-count Earth
  curvature or confuse it with shower-front curvature.
- The 10,000-trial synthetic result repeats noise on one fixed geometry/direction;
  it is not a 10,000-event population result.
- Example event `081847956000` is unblinded development data, not a hidden test.
- Realistic validation needs both known truth and detector-level measurements.
  A fair comparison with Auger additionally needs comparable official results on
  the same events. Access to such a matched sample is not yet established.
- Lower timing residuals alone do not prove better direction reconstruction.
- Null or negative physical/ML improvement is a valid scientific conclusion.

## Evaluation safeguards

Preserve frozen event identifiers, group repeated representations of the same
physical/simulated shower, and create a target-free execution manifest with a
separate reference store before population evaluation. Reserve a non-overlapping
final benchmark before broader exploration. Tune only on development/validation
data; freeze the entire analysis procedure before opening a test. Previously
opened cohorts are historical benchmarks, never new untouched evidence.

## Definition of done for Phase 1

- Complete the exit criteria of all 14 research stages, not only the initial
  plane-front integration or an application-ready intermediate report.
- Deliver tested physical/learned methods, protected cohorts, uncertainty and
  failure studies, frozen final comparisons, and documented limitations.
- Publish reproducibility instructions, configurations, provenance, figures,
  reports, model/data documentation, and an informal mentor-review package.
- Keep unavailable promised data or unperformed studies explicitly outstanding
  unless a scope change is agreed; do not silently drop an access-limited stage.
- Regenerate the scientific package from a clean environment before application
  development. Positive ML gains, outperforming Auger, publication acceptance,
  and formal mentor endorsement are not requirements for a valid study.
