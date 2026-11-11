# Conference instability and core-dependence protocol

Frozen before new refits, 2026-10-13 (America/Vancouver). This is a targeted,
training-only diagnostic study, not a new validation or test-set evaluation.
The archived `training_pilot_20261011_v1` remains unchanged.

## Selection, fixed before inspecting new fits

Use the archived successful timing-weighted quadratic event summary. Select
the three largest complete leave-one-out direction shifts (ties: event ID),
including known extreme event 081881294400. Select the two largest full-fit
nominal reduced chi-squares among events with at least seven selected stations
and complete leave-one-out outputs. For each distinct station count in the
three influence cases, add one stable control: among events of that count with
complete LOO and maximum shift below 1 degree, choose the one nearest their
median shift (ties: event ID). If none exist, use the lowest-shift event at that
count and label the fallback. Keep selection-role overlaps; deduplicate events.
Do not select on agreement with the published direction or on new outcomes.
All selected IDs must occur in the frozen pilot manifest with split `train`.
No validation/test event files are read, downloaded, fitted, or unblinded.

## Experiments

1. For every selected event, preserve archived full and every LOO result. Join
   selected-station ID, x/y/z, t, dt, signal, signal uncertainty, saturation and
   selected flag from the same hashed raw JSON. Never remove influential points
   from the baseline or call them faulty solely because they are influential.
2. Refit the full event and the archived maximum-influence omission with the
   unchanged public quadratic fitter. Repeat with tolerances 1e-12, max 10000
   evaluations, and curvature seeds (1, 25, 100, 500, 2500) ns at 1 km. Save every
   optimizer attempt, not only the chosen solution.
3. Independently profile time and nonnegative curvature analytically at each
   trial direction; optimize only two sky slopes with centered timestamps.
   Start at zeniths 20/50/75 degrees and azimuths 0/90/180/270 degrees, plus the
   archived full and omitted-fit directions. Retain successes and exceptions.
   Compare objective and direction, not solver success alone. Agreement among
   starts is evidence, not proof of a global minimum.
4. Profile the exact conditional objective along 101 spherical-interpolation
   points joining full and omitted directions, separately on full and omitted
   data. Refit time and curvature at every direction. These are diagnostic
   profiles, not likelihood confidence intervals or chi-square p-values.
5. For both full and omitted data, refit the public model after fixed core x/y
   offsets (0,0), (+/-50,0), (0,+/-50), (+/-100,0), (0,+/-100) metres, holding z
   fixed. These scenarios are sensitivity probes, not calibrated core errors.
6. Report column-normalized weighted Jacobian singular values and condition
   numbers for fixed-core four-parameter fits and an augmented six-parameter
   Jacobian including core x/y. The augmented calculation is a local
   identifiability diagnostic, not an independent six-parameter reconstruction.
   Check analytical derivatives against independent central differences.

## Interpretation and possible remedy

A materially lower reproducible objective at another numerical solution would
identify a solver vulnerability and must be reported before changing any fitter.
Persistent, competing low-objective directions or strong core coupling would
instead motivate reliability diagnostics; they do not establish station faults.
No post-hoc station rejection, sigma inflation, curvature cap, or quality cut
will be promoted as a remedy merely to improve this selected sample. A scientific
remedy requires an explicitly recorded follow-up and independent synthetic test.
Previously inspected training events cannot become a held-out evaluation set.

## Reproducibility and limitations

Write selected IDs and roles before fitting; archive protocol, runner and fitting
source hashes, baseline summary/checkpoints, selected raw hashes, package versions,
settings, all attempts, physical station tables, core/profile tables and PNG/SVG
figures under `reports/results/conference_validation_20261013_v1/instability/`.
Run with one worker and one BLAS thread. Retain failed outcomes and never overwrite
a completed run. Nominal degrees of freedom are N-4; boundary constraints and
real-data model error preclude unqualified chi-square probability claims.
The method remains Auger-core-assisted and uses Auger's station selection.
LOO is conditional on that core/selection, not end-to-end independent validation.
Targeted case selection cannot estimate prevalence; prevalence comes only from
the already complete 711-event training analysis.

## Post-hoc mechanism follow-up, approved before its simulation results

After the primary six-case diagnostic was completed, the three unstable layouts
were found to lose a near-core, high-leverage station. The following **post-hoc
hypothesis test** is separate from the original selection and not evidence of
population prevalence, detector realism or a newly validated quality cut.

Use exactly the primary study's three top-influence layouts plus its matched
stable seven-station control. Reuse their measured station positions and stated
dt, and choose the published core coordinates as a fixed **synthetic generator
core**, not as real-event truth. Generate a quadratic front with chosen truth
zenith=30 degrees, azimuth=45 degrees, A=200 ns at 1 km and core time=100000 ns.
For each layout use 200 Gaussian draws, seed 20261013 with one SeedSequence child
per event ID in sorted order. For each draw fit all seven stations and then omit
the station already identified by the primary study; share every remaining noise
realization. Thus 800 paired data sets yield 1600 public default-fitter calls.
All six-station omissions meet the fitter's unchanged minimum count.

Retain all failed outcomes and optimizer attempts. Report true angular errors,
curvature, nominal reduced chi-square and rates of error >1 degree (threshold
fixed before the experiment). For successful paired draws report median
omitted-minus-full angular error and its paired percentile-bootstrap 95% interval
using 2000 resamples, independent seed 610132026; also bootstrap the difference
in >1-degree error rates. These are finite-toy-sample uncertainty intervals, not
detector calibration or causal proof about the real saturated stations. No
threshold, direction, noise model or core will be tuned after seeing results.
Preserve this follow-up in a separate `instability/anchor_ablation/` folder with
its own protocol, source snapshots, inputs, attempt records, figures and receipt.
