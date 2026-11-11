# Conference reliability follow-up: Stages A and B

Authorized 13 October 2026 after the original conference study was sealed.
This is a separate follow-up, not a replacement of that study or a claim that
the whole fourteen-stage research programme is complete.

## Questions and endpoints

1. **Stage A:** Do local, fixed-core, Gaussian direction confidence regions
   attain their nominal 68% and 95% coverage on fresh controlled simulations?
   Model mismatch, weak geometry, and boundary cases remain in the analysis.
2. **Stage B:** Can a simple rule using reconstruction diagnostics alone warn
   about large direction errors on independent synthetic evaluation cases?
   A development-only threshold is frozen before evaluation generation and
   assessment. Evaluation changes geometry and direction as well as random seeds.

The individual protocols specify the exact finite scenario grids, sample sizes,
seeds, warning thresholds and decision criteria before their scientific runs.
There is no requirement for a favourable result. Undercoverage, missed failures
and an unusable warning rule are reportable outcomes, not prompts for tuning
against evaluation data.

## Protected boundaries

- Preserve all files in `reports/results/conference_validation_20261013_v1/`
  and every live source covered by its seal. Its manifest SHA-256 is
  `e516716c090a16d4ae57d36c956f573593d7383bd1b1e0068fe9d4059c30c251`.
- The previous seal verifies 736 artifacts/live sources, 4,130 historical
  files, unchanged raw-event inventory, and unchanged Git HEAD. This check
  passed immediately before the follow-up work.
- Write follow-up outputs only under
  `reports/results/conference_reliability_20261013_v1/`; use new modules,
  tests, protocols and conclusion documents, leaving the fitter unchanged.
- Do not read the 145 protected validation or 144 protected test events.
  These studies generate mathematical station timings and do not require
  any measured event or Auger direction/core reference.
- No commits, staging, pushes or external messages are part of this work.

## Statistical interpretation

The conditional uncertainty calculation treats the supplied synthetic core
and reported station standard deviations as known. It marginalizes the
fitted reference time and curvature as nuisance parameters. It does **not**
include uncertain core position, detector calibration, unknown front shape,
selection effects, or a calibrated air-shower/detector simulation.

The local covariance uses the full weighted model Jacobian with rank checks
and singular-value decomposition. It is not multiplied by reduced chi-square.
Nominal two-dimensional confidence ellipses are approximate local Gaussian
regions, not guaranteed confidence sets in a nonlinear or multimodal problem.
Coverage testing is the experiment, rather than an assumption of correctness.
Curvature boundaries are explicitly identified.

Stage B never receives simulated truth in its runtime warning function.
Truth is allowed only for development and evaluation scoring. A warning is not
automatic station rejection, a change to the fitted direction, or evidence
that the detector measurement is corrupt. Report all attempts and failures,
the unflagged fraction, false warnings and missed large errors. Any reduction
of error after filtering must be accompanied by its loss of retained events.

Monte Carlo intervals concern the finite specified synthetic scenario
population. They are not estimates of true Auger pointing performance or a
complete systematic-error budget. A fresh seed within a reused layout does not
by itself establish generalization to a new geometry.

## Reproducibility and stopping point

Each study archives inputs, raw fit records, exact settings, source/protocol
snapshots and hashes. The combined follow-up will add independent numerical
replay checks, tests and lint receipts, figure inspection, an unchanged-original
seal check, and a separate follow-up manifest. Source changes needed after a
run must be identified; scientific changes require a new output directory.

Finish with one coverage figure, one warning-performance figure, numerical
tables and explicit promotion/non-promotion conclusions, then freeze. Do not
expand into machine learning, an unconstrained free-core fit or a broad search
for an artificially favourable warning threshold within this follow-up.

## Method references

The local-linear nature of nonlinear least-squares covariance, the distinction
between absolute measurement uncertainties and residual rescaling, and the
warning about rank deficiency are described in the
[SciPy covariance documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html).
The nominal two-dimensional region uses quantiles of the
[chi-square distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html)
with two degrees of freedom. These references motivate the approximation;
they do not validate coverage for our model or scenarios.
