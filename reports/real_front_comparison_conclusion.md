# Real-event curvature comparison: scientific conclusion

Final audited run: [real_front_comparison_20261010T201113_597655Z](results/real_front_comparison_20261010T201113_597655Z/).

Notebook: [06_compare_real_event_front_models.ipynb](../notebooks/06_compare_real_event_front_models.ipynb).
Design: [frozen protocol](../docs/real_front_comparison_protocol.md).

## Design and information dependencies

The previously examined event 081847956000 and 19 preselected training events
were reconstructed with plane and nonnegative quadratic timing fronts, using
both timing-uncertainty and uniform weighting. The 19 events were selected by a
deterministic stratified rule before inspecting fit outcomes, from the existing
pilot's train split with at least seven officially selected stations. They are
not a representative population sample or a protected validation/test set.

The quadratic fits used the released `sdrec.x/y/z` core in metres. This is an
**Auger-core-assisted** comparison: official core and station selection are
inherited. Official direction, radius, and station shower-plane distances were
not supplied to either optimizer. Times, uncertainties and selected stations
were identical across models; no extra rejection or uncertainty rescaling was
performed. Reference-direction separation is not true-direction error.

## Focus event: substantial timing improvement, worse reference agreement

| Timing-weighted diagnostic | Plane | Quadratic |
|---|---:|---:|
| Nominal reduced chi-square | 72.9305 | 4.6522 |
| In-sample raw timing RMS (ns) | 462.776 | 96.714 |
| Conditional held-out timing RMS (ns) | 491.193 | 114.812 |
| Separation from Auger reference (degrees) | 0.263897 | 0.551962 |

The quadratic delay at 1 km was 100.2313 ns. All 24 held-out station folds
succeeded for each method. Curvature explains a substantial part of the timing
structure, but the remaining nominal reduced chi-square is well above one.
The curved direction is farther from the official direction in this event.
Neither direction is established as closer to the unknown physical truth.

The opposite changes in timing agreement and reference separation are not hidden
or used to tune the core. They demonstrate why these diagnostics must be reported
separately rather than treating reduced chi-square as directional accuracy.

## Nineteen additional training events

The focus event is excluded. All medians below are across 19 events, each with
successful paired fits; no station-weighted pooling is used.

| Timing-weighted diagnostic: median over events | Plane | Quadratic |
|---|---:|---:|
| Nominal reduced chi-square | 38.5404 | 2.7903 |
| In-sample raw timing RMS (ns) | 436.327 | 133.264 |
| Conditional held-out raw timing RMS (ns) | 530.581 | 170.583 |
| Conditional held-out mean squared normalized error | 71.9135 | 7.2043 |
| Separation from Auger reference (degrees) | 0.792294 | 0.220176 |

- Quadratic nominal reduced chi-square was lower in **19/19** events.
- Quadratic conditional held-out normalized MSE was lower in **17/19** events.
- Quadratic direction was closer to the Auger reference in **17/19** events.
- These are different comparisons; the non-improving events are not the same.

Reference separation worsened for events 113434887000 (0.711482 to 0.886807 degrees)
and 173064766400 (0.237561 to 0.397699 degrees). Conditional held-out normalized MSE
worsened for 112954615400 (71.4104 to 134.6977) and 130237366100 (143.0402 to
1014.8536). In 112954615400 raw held-out RMS nevertheless decreased: the normalized
and unnormalized objectives measure different aspects of disagreement.

No significance claim follows merely from the win counts. The data are a small,
selected development sample, and the models share reconstruction information
with their reference. Per-event results, uniform-weight comparisons, and every
fit attempt remain in the final run directory.

## Core sensitivity and conditional prediction

For the focus event, moving the fixed core by 100 m along x or y changed the
curved direction by approximately 0.263–0.304 degrees while nominal reduced
chi-square remained approximately 4.61–4.70. Shifts by the released axis
uncertainties (dx=13.83 m, dy=26.07 m) changed direction by about 0.042 and
0.069 degrees, respectively. These are axis probes, not a confidence ellipse;
core covariance and vertical uncertainty were not inferred.

Held-out station times are excluded from their respective timing fits. However,
the core and station selection remain those from the original full Auger event.
Thus these are **conditional held-out predictions**, not independent end-to-end
cross-validation. Dividing a held-out residual by its detector timing uncertainty
does not include prediction uncertainty and is not a calibrated predictive pull.
Its mean square is not reduced chi-square. Overlapping station folds are not
independent experimental events.

## Numerical correction and reproducibility

The first development run exposed a plane-fitter bug: tiny finite-difference time
perturbations vanished when added to large absolute timestamps, causing false
Jacobian rank deficiency and undefined reduced chi-square. The residual function
now stays in centred time during optimization. The plane equation, measurements,
weights and parameter count are unchanged. New tests check the time derivative,
rank, direction and prediction invariance at positive/negative large time offsets.
This correction changed the focus plane direction by only about 0.000007 degrees
relative to the earlier archived result; historical outputs were preserved.

Verification of the final run:

- All eight code cells ran in a fresh kernel; four figures were saved and visually checked.
- **1,072/1,072 fits succeeded**: 80 full fits, 832 leave-one-out fits, 160 core probes.
- No nested-objective violations occurred.
- **348 tests passed** with warnings treated as errors; source/tests/notebook lint passed.
- An independent read-only audit replayed **240 fits** with independently expressed
  timing predictions, recomputed all **80 held-out summary rows**, and verified
  **209 artifact hashes** and the saved notebook against its executed archive.
- No validation/test events were fitted; all preselected events and failure
  denominators are preserved.

The first exploratory run (`20261010T191401_384396Z`) is not for final scientific
reporting because of the rank-diagnostic bug. The `20261010T200925_870156Z` run
contains corrected numerical results but is superseded by the final figure and
formatting pass. The run registry identifies the authoritative output directory.

## Defensible poster conclusion and next gate

In this preselected, core-assisted development sample, a quadratic front improves
timing agreement and usually improves conditional timing prediction and agreement
with Auger's direction. It does not resolve every timing discrepancy, improve
every event, establish physical directional accuracy, or outperform Auger's full
reconstruction. Synthetic known-truth controls and measured-event reference
comparisons must remain distinct on the poster.

Investigate the two adverse held-out cases, remaining structured residuals and
core dependence before adding further flexibility or freezing the larger pilot
procedure. Preserve plane and quadratic baselines. Do not force chi-square toward
one through post-hoc uncertainty rescaling or omit unfavourable events.
