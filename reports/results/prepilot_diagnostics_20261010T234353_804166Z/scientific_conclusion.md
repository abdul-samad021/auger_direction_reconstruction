# Pre-pilot diagnostic results

Run: `prepilot_diagnostics_20261010T234353_804166Z`. Previous run remains immutable. Only the original
focus and 19 preselected training events were used. No protected validation/test
events and no 1,000-event run were processed.

## Fixed reference direction

For the focus event, the free-direction timing-weighted quadratic chi-square is
93.043393. Holding Auger's published SD direction fixed and
refitting core time plus curvature gives 136.828167;
the objective penalty is 43.784774. The timing RMS changes from
96.714 to 116.101 ns. Fixed-direction curvature
delay at 1 km is 97.481 ns.

This is a reference-conditioned diagnostic, not blind validation or proof that
either direction is true. No naive delta-chi-square significance is assigned.
Full results for both weighting modes and all 20 events are preserved.

## Station influence

The largest focus-event leave-one-station-out direction change is
0.147780 degrees, at station
822. Complete fold-level direction
changes, residuals, signal, dsignal and saturation metadata are retained in
`station_influence.csv`; `influence_summary.csv` includes every event. Nothing
was rejected or reweighted using these diagnostics.

## Signal/core experiment — not a promoted reconstruction

Of 120 fixed-shape real-event models, 120
converged numerically; only 114 passed the recorded numerical/core
quality checks. 6 reached a core-domain boundary. Convergence
must not be described as a valid physical reconstruction. All six uncalibrated
beta/gamma settings are reported. For the focus
event their estimated x/y cores are separated from the Auger core by
24.76 to
136.22 metres.
The corresponding reference-direction separations range from
0.275147 to
0.499780 degrees. These ranges are
sensitivity results, not uncertainty intervals and not a search for a winner.

For the preregistered central shape (beta=-3, gamma=1), the full chain was
refitted without each held-out station's time AND signal. 208
of 208 folds succeeded; 20 of 20 events have complete folds.
Its held-out normalized timing MSE improved on the published-core-assisted
quadratic baseline in 6/20 complete events. Both methods retain
official station selection and published core z; baseline additionally inherits
the full-event x/y core. This is not independent end-to-end detector validation.

The signal objective is a fixed observed-log-error surrogate, not Auger's full
likelihood. Missing non-triggered-detector status, saturation recovery flags,
calibrated slope dependence and signal asymmetry prohibit promotion of this
model based solely on smaller residuals or reference separation. `sat=2` stations
were excluded from signal fitting only; their timing rows were unchanged.

## Controlled truth tests

Timing controls: 2232/2232 fits succeeded over
two geometries, three directions, four generators and three fitting methods,
with 30 paired noise realizations plus one noise-free check per case. The exact
expanding sphere uses an independent distance formula; the coherent-gradient
case tests a systematic that can shift direction while leaving a small residual.
All cases and failures are reported, not just matched-model recovery.

For the coherent-gradient generator, the median across six case-median angular
errors of the true-core quadratic fit is 2.1468
degrees, while the median across their mean nominal reduced chi-squares is
1.1769. This is a controlled
counterexample to treating chi-square near one as proof of directional accuracy.
It is not evidence that this particular systematic exists in the Auger data.

Signal controls: 120/120
end-to-end toy chains succeeded at two directions with matched/mismatched lateral
shapes. These are controlled station-level toys, not realistic air-shower and
detector Monte Carlo. Synthesis truth never enters the tested chain's direction
or horizontal-core estimation. Known core z and generated uncertainties do.

## Pilot release decision

**The experimental signal-core estimator is not promoted.** Retain the tested
plane and explicitly published-core-assisted quadratic baselines. Do not replace
the core or tune beta/gamma using the published direction. Do not force nominal
reduced chi-square to one by clipping stations or scaling uncertainties.

The exact baseline settings and failure/reporting policy are now frozen in
`pilot_baseline_contract.json`, with a target-free 1000-row execution list in
`pilot_execution_target_free.csv`. That is readiness for a **labelled baseline
comparison**, not a certification of a solved or independent reconstruction.
The next batch implementation must enforce that contract, checkpoint failures,
and preserve protected splits. No protected outcomes are exposed for tuning;
the future ML test split must not become a development set. Lower timing
objectives alone cannot certify more accurate physical directions.

Primary sources: https://opendata.auger.org/data.php and
https://arxiv.org/abs/2007.09035 (especially Sections 5.1–5.2).
