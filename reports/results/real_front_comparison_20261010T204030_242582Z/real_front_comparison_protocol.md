# Real-event plane-versus-quadratic development protocol

## Question and scope

Does adding a nonnegative quadratic shower-front term explain the timing mismatch
of the first development event, and does that finding repeat in a preselected
training-only sample? Direction agreement with Auger is a secondary descriptive
comparison, not an error measurement against physical truth.

This is an **Auger-core-assisted development analysis**, not an independent
reconstruction or a protected test. The station selection and fixed reconstructed
core both come from Auger. The official direction, curvature radius, and
shower-plane station distances are never optimizer inputs.

## Inputs frozen before fitting

- Focus event: `081847956000`, already unblinded in Notebook 03.
- Additional events: 19 deterministic, stratified selections from the existing
  pilot's **train** split, requiring at least seven selected stations in its
  summary so leave-one-out fitting can retain six. Exclude the focus event.
- Selection uses event identity, split, station count, and existing zenith and
  multiplicity bins, not fit outcomes or proximity to the reference direction.
- Freeze identities and the pilot-manifest checksum in
  `data/manifests/real_front_development_v1.json` before downloading/fitting.
  No replacement of unavailable, malformed, or failed events after outcomes
  are known. Record their failures and denominators.
- Use the existing strict timing adapter and `OFFICIAL_SELECTED` stations.
  Do not change uncertainties, reject additional stations, or flatten times.
- Load `sdrec.x/y/z` separately as the external fixed core, in metres in the
  released site frame. Do not substitute UTM easting/northing or absolute
  altitude. Do not add an Earth-curvature correction: the precise coordinate
  export transformation remains an outstanding systematic issue.

## Models and recorded settings

For propagation unit vector u and d = station position minus core position:

    plane:     t = t_ref + (r - r_ref) . u / c
    quadratic: t = t_core + d . u / c + A |d cross u|^2 / (1000 m)^2

Fit the direction and time independently for each model. In the quadratic model,
also fit A >= 0, recomputing axis distances from each candidate direction.
Use both timing-uncertainty and uniform weighting, with the existing tested
fitters and their default recorded options (six-station minimum for both).
The primary comparison is timing-weighted; uniform is a comparator.

Retain all optimizer attempts, quality flags, boundary solutions and failures.
Check that the nested quadratic objective does not exceed the corresponding
plane objective beyond recorded numerical tolerances. Do not substitute reduced
chi-square for the minimized objective in this check.

## Diagnostics fixed in advance

1. Full fits: direction, curvature delay at 1 km, raw timing RMS, chi-square,
   nominal degrees of freedom N-3/N-4, residuals and geometry diagnostics.
2. Spatial residual plots and timing residual versus horizontal core distance.
   Horizontal distance is a common plotting coordinate, not a substituted
   shower-plane distance in either optimization.
3. Leave each selected station out in turn; refit both models with both weights
   using only retained timing measurements, then predict the omitted time.
   Report held-out RMS and mean squared residual divided by the stated timing
   uncertainty, without a degrees-of-freedom correction. These normalized
   errors are **not predictive pulls**: prediction uncertainty is not included.
   Core and station selection remain inherited from the full Auger event, so
   this is conditional held-out timing prediction, not leakage-free end-to-end
   cross-validation. Folds overlap and are not independent trials.
4. Timing-weighted quadratic core sensitivity: fixed +/-100 m x/y shifts and,
   when released, +/-dx and +/-dy axis shifts. Keep z unchanged. These are
   probes, not confidence regions or a covariance model; no xy covariance or
   vertical uncertainty is inferred. Compare each with the nominal fitted
   direction, not with the reference to choose an optimal core.
5. Save predictions before loading the published direction for evaluation.
   This ordering does not reblind the already examined focus event.

## Reporting and stopping rules

Report per-event paired changes and all failures. Aggregate at the event level,
not by treating stations, overlapping folds, or solver starts as independent
events. Keep the focus event separate from the 19 newly selected events in
aggregate reporting. No significance claim or population angular resolution
follows from this small, selected development sample.

A smaller in-sample objective is expected from a nested, more flexible model.
It is not by itself proof of physically better directions. Boundary solutions,
core uncertainty, correlated timing and model misspecification also limit
ordinary chi-square interpretations. No target of forcing chi-square to one,
post-hoc uncertainty rescaling, or selection of only improved events is allowed.

Run this experiment, examine remaining discrepancies, and document limitations
before deciding whether to freeze a method for the larger pilot. Do not run
protected validation/test events as part of this notebook.

## Numerical correction discovered during integration

The first development run exposed a false rank-deficiency diagnostic in the plane
fitter: at absolute timestamps around 5e8 ns, adding the solver's approximately
1.49e-8 ns time-offset perturbation back to an absolute time could round it away
(float64 spacing was approximately 5.96e-8 ns). This created a zero time-derivative
column even for identifiable geometry. The optimizer residual is now evaluated
entirely in centred time, restoring absolute timestamps only for public outputs.
The physics equation, inputs, weights and parameter count are unchanged.

Regression tests cover both weights, positive/negative large time offsets,
direction and prediction invariance, and the expected offset derivative -1/dt.
Final reporting must use the fresh rerun after this correction, not the preliminary
run with undefined plane reduced chi-square. Historical source snapshots are
preserved; the older plane-only notebook is not silently rewritten.

## References

- [Auger public field documentation](https://opendata.auger.org/data.php): released
  station/core coordinates and timing fields.
- [Surface-detector reconstruction paper, section 5.1](https://arxiv.org/abs/2007.09035):
  physical motivation for the paraboloidal front. This experiment is not a
  reproduction of the full Auger reconstruction.
- The project's Auger-team correspondence supports using the released local
  x/y/z convention; it did not resolve every coordinate-export detail.
