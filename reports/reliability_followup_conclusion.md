# Directional reliability follow-up — scientific conclusion

Completed 13 October 2026 Pacific time (14 October UTC). These are Stages A and B
of the authorized conference follow-up, mainly within Stage 12 of the original
fourteen-stage roadmap. The preceding conference study is preserved unchanged.

## Main result

**A good timing fit, a small local uncertainty, and an accurate reconstructed
direction are different properties.** Our conditional uncertainty procedure
performs approximately as expected in the matched toy model, but can be severely
overconfident when its mean-front or timing-uncertainty assumptions are wrong.
A development-locked local-uncertainty warning did not meet the prespecified
requirements and is **not promoted as a production reliability gate**.

This strengthens the conference study by testing, and limiting, a proposed
remedy rather than assuming that adding error bars solves directional instability.
It is not a claim to have improved true Auger angular resolution.

## Stage A: are nominal direction regions calibrated?

We constructed two-dimensional local Gaussian direction regions using the full
weighted timing Jacobian. Singular-value decomposition marginalizes the fitted
time and curvature; the core is fixed to its chosen synthetic truth. Covariance
is not rescaled to make reduced chi-square equal one. Coverage is evaluated with
the spherical logarithm at the fitted direction, not separate azimuth differences.

The study has 24 prescribed scenarios and 200 attempts each: four geometries,
two directions, and three regimes. All **4,800 fits and covariance calculations
succeeded**. Three curvature-boundary cases are retained and flagged. All counts
below include them; the saved tables also separate interior and available cases.

| Generated/reported regime | Covered by nominal 68% region | Covered by nominal 95% region |
|---|---:|---:|
| Matched Gaussian mean and uncertainties | 1,080 / 1,600 (67.50%) | 1,528 / 1,600 (95.50%) |
| Imposed asymmetric mean front | 97 / 1,600 (6.06%) | 293 / 1,600 (18.31%) |
| Reported timing sigma half its actual value | 396 / 1,600 (24.75%) | 846 / 1,600 (52.88%) |

These are descriptive averages over eight equally represented fixed settings,
not estimates for a detector-event population. The regimes share noise draws;
there are 1,600 independently generated Gaussian vectors evaluated under three
paired regimes, not 4,800 independent comparisons. Per-scenario Wilson intervals
are saved and plotted; no pooled independent-binomial interval is claimed.
Matched-case nominal 95% coverage ranges from 93% to 98.5%; this finite check is
not a guarantee of calibration in every geometry or outside the chosen grid.

Halving all reported sigmas leaves the ideal least-squares minimum unchanged but
halves the local ellipse axes. In a regular two-dimensional linear-Gaussian
limit, nominal coverage p then becomes 1-(1-p)^(1/4): approximately 24.8% and
52.7% for p=68% and 95%. The observed undercoverage is consistent with that
mechanism, without tuning the method to force agreement.

An informative single setting is the anchored-ring layout at zenith 25 degrees:

| Regime | Nominal 95% coverage | Mean nominal reduced chi-square | Median true angular error |
|---|---:|---:|---:|
| Matched | 194 / 200 (97%) | 1.0191 | 0.1771 degrees |
| Asymmetric mean | 6 / 200 (3%) | 1.0157 | 0.6817 degrees |

The asymmetric coverage's 95% Wilson interval is approximately 1.38–6.39%.
The near-unity chi-square does not expose the incorrectly narrow direction
regions. **Three-percent coverage does not mean 97% catastrophic pointing
errors**: the median absolute angular error is about 0.68 degrees in this case.
It means the claimed conditional uncertainty fails to represent actual error.

## Stage B: can a simple warning identify large errors?

One rule uses only fitted quantities: warn if the nominal 95% ellipse major
semiaxis exceeds a threshold, or if fitting/uncertainty fails or curvature lies
on its boundary. Truth never enters the runtime warning function.

Nine thresholds were considered on 3,600 development fits only. None attained
the predeclared targets of at least 90% sensitivity and at most 30% false-warning
rate for true errors strictly above one degree. The prescribed exploratory
fallback, a one-degree uncertainty threshold, was locked before generating
3,600 validation cases with changed counts, directions, rotated/jittered layouts
and new random streams. These are new instances of the same chosen geometry
and mismatch families, not wholly unseen physical families.

All **7,200 fits succeeded**. Independent validation of the frozen rule gives:

- Detected 1,612 / 2,041 large errors: **78.98% sensitivity**.
- Warned on 688 / 1,559 results with error at most one degree:
  **44.13% false-warning rate**.
- Retained 1,300 / 3,600 results: **36.11% retention**.
- Left 429 / 1,300 retained results above one degree: **33.00% retained risk**.

The unfiltered validation mixture has 56.69% above one degree. Reducing that
fraction by retaining only 36.11% of cases is not an improvement of the original
point estimator and is not enough to establish a safe selection rule. The
mixture is deliberately difficult and is not an estimate of real-event risk.

| Validation regime | Retained / attempted | Large errors missed / retained |
|---|---:|---:|
| Matched mean and uncertainties | 400 / 1,200 | 0 / 400 |
| Imposed asymmetric mean | 400 / 1,200 | 399 / 400 |
| Underreported timing uncertainties | 500 / 1,200 | 30 / 500 |

Zero observed errors in the matched retained sample is not a zero-risk proof
(its approximate 95% Wilson upper limit is 0.951%). Under the deliberately
strong asymmetric stress, virtually every unflagged result exceeds one degree,
although mean nominal reduced chi-square across that regime is 1.371. Its
false-warning statistic has only one non-large-error example and is not a
precisely estimated zero. Regime-pooled comparisons preserve the pairing and
do not use inappropriate independent-binomial confidence intervals.

## Scientific decision and limits

1. Keep the existing plane baseline and conditional quadratic fitter unchanged.
2. Retain the local covariance as an explicitly approximate research diagnostic,
   not a calibrated total error budget for real Auger events.
3. **Do not enable the tested warning as a production gate.** Do not change its
   threshold using validation, delete inconvenient stations, or inflate timing
   uncertainties merely to improve reported chi-square.
4. Future discrepancy-aware uncertainty or calibrated core/signal modelling
   needs a new protocol and fresh evaluation. This experiment does not prove
   every possible reliability warning must fail.
5. Freeze these results for the conference. Machine learning and the rest of the
   full roadmap remain future work; the negative warning result is not a reason
   to extend today's study until a favourable remedy appears.

These are mathematical timing simulations with chosen geometry, front shape,
noise, and an exactly supplied core. They do not model a complete air shower,
detector response, unknown core uncertainty, or selection/calibration pipeline.
Neither the 145 protected real validation events nor the 144 protected real
test events were opened. The earlier real-data curvature study remains
Auger-core-assisted, not wholly independent truth reconstruction.

## Reproducibility and verification

The canonical follow-up artifacts are under
`reports/results/conference_reliability_20261013_v1/`:

- `stage_a/final_v2/`: canonical 4,800-fit coverage experiment, inputs, full
  attempt diagnostics, summaries, sources and vector/raster coverage figures.
- `stage_b/`: canonical 7,200-fit warning experiment, separately archived
  development/evaluation inputs, frozen policy, diagnostics and figures.
- `independent_audit.json`: all 12,000 canonical successful fits independently
  replayed. The audit uses nuisance-projected QR information rather than the
  study's full SVD covariance, and recomputes objective values, angular errors,
  coverage counts/intervals and warning decisions/selection.
- `release/`: final quality-gate, source-version and integrity receipts.

Maximum relative discrepancy in the Stage A covariance replay is 1.12e-14;
the largest scaled objective discrepancy across both studies is below 3.5e-12.
The warning policy hash is
`12348c3b22f9c37f6a34a486646eb3e54890066fe925c740963fafb1542161b3`;
its lock precedes validation generation, verified independently.

Stage A initially completed all fits but its plot encountered a tiny negative
error-bar width from floating-point rounding. The first raw outputs and their
report recovery are preserved. A plotting-only clamp was followed by a clean
deterministic rerun: all 27 scientific artifacts (24 input arrays, raw trials,
summary and optimizer attempts) are byte-identical. This is **one experiment**,
not 9,600 independent fits of evidence. Source checks explicitly permit only
that plotting-function change between Stage B's archived helper and the current
module; mathematical functions are identical. Smoke runs are also excluded.

The original sealed 736-artifact release and 4,130 historical files verify
unchanged. Full-suite tests, lint, new-file formatting and final provenance
receipts are recorded in the follow-up release. No commits or pushes were made.

## Conference takeaway

**Curvature improves conditional timing prediction, but directional reliability
also requires valid noise and front assumptions. We tested uncertainty regions
and a frozen warning rule, found important overconfidence under model mismatch,
and declined to promote an inadequate safeguard.**
