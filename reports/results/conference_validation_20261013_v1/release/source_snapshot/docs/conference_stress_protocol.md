# Conference controlled stress study — frozen design, 2026-10-13

This protocol is written before inspecting outcomes. The study accesses no real
events, protected split, official direction, or official core. Earlier outputs
and production fitters remain unchanged. Coefficients below are deliberately
uncalibrated stress settings, not measured Auger detector physics.

## Factorial design and estimands

- Three deterministic layouts: well-spread, elongated, and one-sided relative
  to the fixed true core `(120,-80,0)` m.
- Two counts, 7 and 13; two sky directions `(25,20)` and `(55,210)` degrees.
- Six regimes below, 100 independent noise realizations per scenario.
- 72 scenarios, 7,200 paired datasets, 28,800 requested fits: plane/quadratic
  crossed with timing/uniform weighting. Every method receives identical
  measurements for a particular dataset. The quadratic receives the exact
  synthetic core; neither fitter receives true direction or curvature.
- 12 geometries/directions × two exact fronts × four methods = 96 noiseless
  control fits. Only a matching model is required to recover truth; the plane
  fitted to curved truth is a deliberate mismatch, not an exactness gate.
- Seed 20261013, with distinct keyed streams for scenario trials and bootstrap.
  The configuration, geometry, source hashes and package versions are archived
  before fitting. Per-scenario files are atomic and completed files can resume
  only under an identical protocol/source/configuration fingerprint.

Stations follow golden-angle rays, radius `250+145*j` m, angle
`j*pi*(3-sqrt(5))`, height `12*sin(1.7*j)` m for j=0,...,12. The 7-station subset
uses even j. Elongated multiplies x by 1.8 and y by 0.25. One-sided multiplies
x,y by 0.7 and translates x by +2100 m. These are three examples, not random
draws from the distribution of real array geometries.

## Independent generator

Let `d_i=r_i-r_core`, `u=-s_true`, `l_i=d_i.u`, and
`rho_i=sqrt(|d_i|^2-l_i^2)`. Independent scalar arithmetic constructs

`mean_t_i = 100000 ns + l_i/c + 80 ns*(rho_i/1000 m)^2 + asymmetry_i`.

Here `c=0.299792458 m/ns`. This does not call either fitter's timing predictor
or the project's quadratic generator. A transverse unit basis vector is
`e_theta=(cos(theta)cos(phi),cos(theta)sin(phi),-sin(theta))`.
The asymmetric regime adds

`asymmetry_i = 30 ns * rho_i*(d_i.e_theta)/(1000 m)^2`.

Equivalently it is an azimuthally varying quadratic-amplitude perturbation.
It is zero on the axis, is deterministic mean-front mismatch, and is not
random noise. The 30 ns amplitude is not inferred from Auger events.

## Actual uncertainty versus reported uncertainty

Baseline `sigma_i = 8 + 2*(i mod 5)` ns for array row index i. For radial regimes,
set `r=rho_i/1000 m`, toy signal proxy `S_i=[1+(rho_i/700 m)^2]^(-1.5)`, and

`sigma_i = sqrt(8^2 + (12*r^2)^2 + (8/sqrt(S_i))^2)` ns.

The proxy is dimensionless and used only to define a controlled uncertainty
pattern. No signal likelihood or realistic particle sampling is claimed.

1. `calibrated_gaussian`: symmetric quadratic mean; baseline actual sigma and
   reported dt; noise sigma*Normal(0,1).
2. `asymmetric_mean`: asymmetric mean above; baseline actual sigma and correctly
   reported dt; noise sigma*Normal(0,1).
3. `radial_calibrated`: symmetric quadratic; radial actual sigma and correct dt;
   Gaussian noise.
4. `radial_underreported`: same physical noise law as regime 3; reported
   `dt_i=sigma_i/[1+0.8*r^(1.5)]`. This changes reported precision, not actual noise.
5. `heavy_tail_t5`: symmetric quadratic; baseline sigma and correct dt; noise
   sigma*sqrt(3/5)*StudentT(df=5), with exactly zero mean and unit variance.
6. `centered_skew`: symmetric quadratic; baseline sigma and correct dt; noise
   sigma*(Exponential(scale=1)-1), with exactly zero mean and unit variance.

Regimes 3 and 4 use the same Gaussian standardized draws at a fixed geometry,
direction and trial, enabling a direct miscalibration contrast. The Gaussian,
asymmetric and radial regimes share these draws but have different means/scales.
Other distributions use distinct streams. All four fitting methods always
share the exact observed dataset within a regime.

## Reporting and gates

Retain every failed attempt with category/message/optimizer diagnostics when
available. Summaries report requested, successful and paired-valid counts.
Do not silently treat a failure as zero angular error. Numerical convergence,
quality flags and scientific adequacy are separate quantities.

For each scenario/method report true angular error median/p68/p95, nominal
reduced chi-square and raw timing RMS. For predeclared paired method contrasts,
report median per-trial angular improvement and a 95% percentile bootstrap
interval (2,000 resamples of paired trials). Intervals concern Monte Carlo
sampling for this fixed synthetic scenario, not detector-population uncertainty
or a simultaneous multiple-comparison discovery claim. Failure-conditioned
contrasts never substitute for complete-case success rates.

Independent checks verify unit/downward vectors, residuals, objective arithmetic,
and the nesting of plane within nonnegative quadratic models. Exact matching
controls, zero-asymmetry, zero-curvature, translation and distribution tests are
mandatory. Nominal N-3/N-4 diagnostics are not calibrated significance tests:
misspecification, non-Gaussian errors and nonnegative curvature boundaries matter.
There is no promotion rule based on approaching reduced chi-square one, and no
post-hoc changes to scenarios to improve an outcome.

The conference conclusion will be explicitly conditional on this finite grid.
This study neither estimates independent cores nor proves real-shower accuracy.
