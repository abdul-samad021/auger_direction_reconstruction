# Pre-pilot diagnostic protocol — version 1

This development study is defined before its results are inspected. It does not
authorize, execute, or unblind the 1,000-event pilot. Reuse only the focus event
and 19 training events in `real_front_development_v1.json`; keep the previous
audited run immutable. No event replacement, station rejection based on residuals,
uncertainty rescaling, or selection of favourable outcomes is permitted.

## Questions and comparisons

1. On each of the 20 events, hold the published SD direction fixed and estimate
   only core time and nonnegative quadratic curvature. Compare the objective
   with the previous free-direction result at identical core, stations and
   uncertainties. This is reference-conditioned diagnosis, not a prediction,
   independent cross-validation, or a test of truth. Report raw objective changes;
   do not assign naive chi-square p-values.
2. Inspect every saved quadratic leave-one-station-out direction change and
   held-out residual. Join by station ID to signal, signal uncertainty and
   saturation. Report all events, highlighting the focus and adverse cases.
   Correlations and station influence are descriptive, not rejection rules.
3. Controlled timing experiment: the actual focus station geometry and a flat
   version of it, sky directions (25,20), (54,54), (60,210) degrees, 30 paired
   noise draws per combination, seed 20261011. Four generators: plane,
   quadratic delay 100 ns at 1 km, exact expanding sphere with matching local
   curvature, and quadratic plus a coherent 100 ns/km eastward timing gradient.
   Compare plane, quadratic at true core, and quadratic at core shifted +100 m
   in x. Known truth is used only for generation and evaluation. All are toy
   station-timing simulations, not particle/detector Monte Carlo. Report failure
   denominators, angular errors, and nominal reduced chi-square separately.
4. Experimental lateral signal model: modified-NKG radial shape from Eq. 5.7 of
   Auger's reconstruction paper, with explicitly uncalibrated fixed slopes.
   Test all six combinations beta in {-2.5,-3,-3.5}, gamma in {0,1}; no best
   combination is chosen by agreement with Auger. Fit core x/y and normalization
   from selected stations with finite positive signal/dsignal and sat 0 or 1.
   Sat 2 is excluded from this signal experiment because the public schema does
   not state whether recovery succeeded. These exclusions never change timing
   station selection. Record every exclusion. Use direction from our blind
   timing-weighted plane fit, and fixed z from the released core (disclosed).
   Refit quadratic timing using each estimated core, with no official x/y
   initialization, direction, energy, or reconstructed station distances.
5. Validate the signal-core implementation on exact known-core synthetic
   signals, translation invariance, degeneracy, invalid inputs, and independent
   predictions. Add noisy matched-shape and mismatched-shape controls using
   fixed seeds. No full joint timing+signal likelihood is promoted yet.

## Scientific limitations

The surrogate uses fixed observed log-signal errors, not Auger's Poisson/Gaussian
and saturation likelihood. Missing operational non-triggered detectors,
uncalibrated slope dependence, possible signal asymmetry, fixed core altitude,
and direction/core dependence prevent claiming an independent Auger-equivalent
reconstruction. Its objective is not a calibrated chi-square. The timing fit's
N-4 is conditional on the estimated core and is not an end-to-end degree count.
Published direction and core are references, not truth. Repeated noise draws
at a fixed geometry are not independent real events.

## Release gate

Automated tests, fresh execution, immutable configuration/source/input hashes,
and explicit failed-fit records are mandatory. Signal-core is experimental and
not automatically substituted into the pilot. After interpreting these outcomes,
freeze a clearly labelled baseline/curvature comparison and failure policy;
resolve any numerical or data-contract failures first. Remaining model mismatch
may be reported rather than forced away. Research validation/test splits remain
untouched until the analysis and claims are frozen.

## Primary sources

- https://opendata.auger.org/data.php (signal/dsignal/sat semantics; reconstruction)
- https://arxiv.org/abs/2007.09035 (Sections 5.1–5.2, especially Eq. 5.7 and the
  detector-status likelihood and core/direction coupling discussion)

## Reporting clarification after the first execution

The first execution exposed signal-core boundary solutions. The finalized report
distinguishes numerical convergence from passing rank/condition/domain checks;
all boundary solutions remain in the tables. No scientific settings, sample,
noise seed, signal slopes, or timing selection were changed. The full-chain
signal test has 208 held-out folds (not 832: that earlier count included four
model/weight combinations). The signal toy uses 30 paired noise realizations
at each of two directions and two lateral shapes, with 15% lognormal scatter.

The handoff freezes only the plane and published-core-assisted quadratic
baselines. A >1 degree leave-one-out direction-change warning is descriptive,
not a primary-outcome cut. Protected split outcomes remain sealed for subsequent
research decisions; the full project's ML test set is not available for tuning.
The signal model remains an experimental negative/robustness result.
