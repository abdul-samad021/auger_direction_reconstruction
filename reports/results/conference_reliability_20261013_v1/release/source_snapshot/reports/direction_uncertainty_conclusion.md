# Conditional direction uncertainty: conference follow-up Stage A

## Research question and scope

Does a local Gaussian uncertainty region for the reconstructed direction have
its advertised repeated-measurement coverage? This study tests that question on
known-truth synthetic measurements, conditional on a fixed true core. It does
not estimate complete detector uncertainty or use any additional real events.

The existing quadratic-front fitter was unchanged. A new, independently derived
tangent-plane timing Jacobian accounts for all four fitted parameters: time, two
direction components and curvature. The angular block of the full SVD covariance
marginalizes the fitted time and curvature. We do **not** multiply the covariance
by the observed reduced chi-square. Regions use chi-square(2) thresholds for 68%
and 95% and compare the true direction using its spherical log-map displacement.

These are local approximations, not proof of Gaussianity or global identifiability.
An algebraically available covariance does not establish that its regions are
calibrated, and neither a boundary nor a second solution branch is cured by SVD.

## Frozen experiment

The protocol was fixed before production results: four toy layouts (well-spread
13 stations, elongated 7, near-ring 6, and near-ring plus a precise near-core
anchor 7), two directions (25°,20°) and (55°,210°), and three prescribed regimes.
Every scenario has 200 independent Gaussian-noise repetitions. The same noise
draws are paired across the three regimes within each layout/direction, not
across layouts. True curvature is 200 ns at 1 km; the chosen core is fixed and
known. Truth is used to generate and evaluate data, never as an optimizer seed.

The regimes separate three questions:

1. **Calibrated Gaussian:** generated mean and reported timing uncertainties match
   the fitted model and actual measurement scatter.
2. **Asymmetric mean:** the same noise plus a prescribed directional mean term
   absent from the fitted model. This is a controlled mismatch, not a claim that
   measured Auger showers have exactly this asymmetry.
3. **Underreported sigma:** the same symmetric measurements as regime 1, but
   every reported timing uncertainty is half its actual standard deviation.

All **4,800 distinct synthetic fits** succeeded and produced evaluable local
regions. Three fits were at the curvature boundary (one in each regime, all in
the 25° unanchored-ring case); they remain in primary counts. Available-interior
coverage is also saved separately. No region was unavailable and no event was
deleted based on its residual, error or fit quality.

## Main results

The following are descriptive equal-count summaries over the eight fixed
layout/direction settings per regime. They are **not** performance estimates for
a physical detector population. No pooled binomial interval is assigned to these
cross-scenario aggregates. Per-scenario 95% Wilson Monte Carlo intervals are
provided in the saved table and figure; they are not simultaneous guarantees.

| Generation / reporting regime | 68% regions containing truth | 95% regions containing truth | Range of scenario 95% coverage |
|---|---:|---:|---:|
| Calibrated Gaussian | 1080/1600 = 67.50% | 1528/1600 = 95.50% | 93.0–98.5% |
| Asymmetric mean | 97/1600 = 6.06% | 293/1600 = 18.31% | 0–72.5% |
| Reported sigma half actual | 396/1600 = 24.75% | 846/1600 = 52.88% | 47.0–60.0% |

The complete per-setting 95% coverage is retained, including every adverse case:

| Layout / true zenith | Calibrated Gaussian | Asymmetric mean | Half-reported sigma |
|---|---:|---:|---:|
| Well-spread / 25° | 94.0% | 0.0% | 55.0% |
| Well-spread / 55° | 94.5% | 0.5% | 47.0% |
| Elongated / 25° | 93.0% | 0.0% | 49.5% |
| Elongated / 55° | 98.5% | 0.0% | 49.5% |
| Ring + anchor / 25° | 97.0% | 3.0% | 57.5% |
| Ring + anchor / 55° | 94.0% | 66.0% | 52.0% |
| Ring without anchor / 25° | 95.5% | 4.5% | 52.5% |
| Ring without anchor / 55° | 97.5% | 72.5% | 60.0% |

### An important counterexample: acceptable timing chi-square, overconfident direction

For the anchored-ring layout at true zenith 25°:

| Quantity | Calibrated Gaussian | Asymmetric mean |
|---|---:|---:|
| Mean nominal reduced chi-square | 1.0191 | 1.0157 |
| Median angular error | 0.1771° | 0.6817° |
| Median 95% major semiaxis | 0.4130° | 0.4112° |
| 95% regions containing truth | 194/200 = 97.0% | 6/200 = 3.0% |
| Per-scenario Wilson 95% interval | 93.61–98.62% | 1.38–6.39% |

Thus the controlled mismatch creates a directional bias while the reported
uncertainty region barely changes. A reduced chi-square near one does not certify
directional coverage. Importantly, **97% noncoverage does not mean 97% of events
have catastrophic angular errors**: the median error in this case is 0.682°.
The failure is severe overconfidence relative to the reported region.

### Underreported uncertainty behaves as expected

Halving every reported sigma changes no relative station weight, so it leaves
the optimum direction essentially unchanged while quartering the covariance and
approximately quadrupling nominal reduced chi-square. In a locally linear
two-dimensional Gaussian approximation, the actual coverage becomes

    P(chi-square(2) <= nominal_threshold/4),

which is about 24.8% for a nominal 68% region and 52.7% for a nominal 95% region.
Observed descriptive rates, 24.75% and 52.88%, agree closely with that mechanism.
This is a calibration sanity check, not a novel uncertainty correction.

## What we can and cannot conclude

- The independently implemented local method has approximately nominal aggregate
  coverage in the bounded, correctly specified scenarios. Individual scenario
  estimates fluctuate at 200 trials; the 68% range is 60.5–72.0%. We do not claim
  exact coverage in every layout or universal calibration.
- Mean-model mismatch and erroneous reported timing uncertainties cause different
  failures. Residual chi-square may expose the latter, yet miss important bias
  in the former. Automatic chi-square rescaling is therefore not a validation.
- This experiment does not resolve the extreme real-event/anchor-ablation
  instability previously documented. Its toy ring is a new chosen geometry, not
  a reproduction of those events, and a local ellipse cannot rule out distant
  minima or reliably describe a multimodal fit.
- The supplied core has no uncertainty here. Real-data core uncertainty, selection,
  detector calibration, correlations and model discrepancy are not represented
  in these conditional regions. Coverage on simulations is conditional on the
  simulator assumptions, not established coverage for measured cosmic rays.
- No new fitter, rescaled error bar, station rejection policy or detector-level
  calibrated interval is promoted from this study. Stage B separately tests
  whether fit-only warnings recognize risky reconstructions on independent
  validation settings; its thresholds must not be tuned on these coverage results.

## Verification, canonical artifacts and reporting-only amendment

- Canonical run: `reports/results/conference_reliability_20261013_v1/stage_a/final_v2/`.
- Independent implementation tests: **25 passed**, including spherical tangent
  finite differences, nuisance-projected information vs full SVD covariance,
  known-sigma scaling, exact recovery, rank failure, boundary flags and explicit
  numerical-covariance failure handling. Source lint passed.
- Canonical run duration recorded by the experiment: **43.62 seconds**. Its
  `protocol_lock.json` archives options, keys, versions and pre-run source hashes.
- All fitted vectors, local covariance entries, region decisions and optimizer
  attempts are saved. Every scenario NPZ preserves actual/raw times, reported
  sigma, actual sigma, geometry, fixed core and true direction.
- `direction_coverage.png` and `.svg` were visually inspected. They show every
  setting and both nominal coverage levels with Monte Carlo uncertainty bars.
- A separate 48-fit smoke run is excluded. The first full run completed all fits
  and tables, but figure rendering stopped on a tiny negative errorbar width from
  floating-point Wilson endpoint roundoff. Its raw files were preserved; a
  standalone recovery renderer completed its artifacts without modifying them.
- After Stage B had completed with the original shared helper snapshot, the only
  experiment-source amendment was clipping **displayed errorbar widths** to zero
  in `_figures`. The helper mathematics, simulation, fit settings and scientific
  summaries did not change. A clean full rerun generated canonical `final_v2`.
  All **27 scientific data files** (24 input NPZs, trials, summary, optimizer
  attempts) are byte-identical across the two full runs. They are duplicated
  computation, **not 9,600 independent trials or additional evidence**.
- `stage_a/rendering_amendment.json` records that audit. Both source snapshots
  and earlier outputs are retained. No original conference-release artifacts,
  protected real-data cohorts, commits or remote branches were changed.

**Poster-ready conclusion:** Local fixed-core direction regions work approximately
as expected under a matched noise-and-front model, but can become strongly
overconfident under controlled mean mismatch—even when timing chi-square remains
near one. Good timing fit quality alone is not a reliable uncertainty certificate.
