# Stage A: conditional directional-uncertainty coverage

Frozen design for the conference follow-up, 13 October 2026. This is a separate
study, not a modification of the sealed conference-validation release. No real
events or protected evaluation cohorts are opened. No production fitter changes.

## Scientific question and estimand

Does the local Gaussian uncertainty ellipse from a fixed-known-core quadratic
timing fit contain the chosen true sky direction in 68% / 95% of repeated noisy
measurements? The ellipse is conditional on the fixed core and reported timing
uncertainties. It is not total detector uncertainty. These are frequentist
repeated-measurement coverage rates, not posterior probabilities for a fixed truth.

At fitted sky unit vector s, choose two deterministic orthonormal tangent axes B.
For d = station minus core, u=-s, l=d.u, rho²=|d|²-l² and A the delay at 1 km:

    t = tc + l/c + A*rho²/10^6
    dt/d(alpha1,alpha2) = (1/c - 2*A*l/10^6)*(-d.B)

The complete Jacobian has columns (tc, alpha1, alpha2, A), each row divided by
reported sigma. Column-normalized SVD is used with relative rank tolerance 1e-10.
The 2x2 angular block of the full four-parameter covariance marginalizes nuisance
time and curvature. No explicit normal-matrix inverse and no residual-chi-square
rescaling. Spherical log-map displacement at the fitted direction is tested
against the ellipse; chi-square(2) thresholds are -2*log(1-p). Ellipse axes are
tangent radians converted to degrees, not isotropic cones.

Algebraic availability does not establish validity: curvature <=1e-6 ns flags
the nonnegative boundary; 95% major semiaxis >10 degrees flags a broad local
approximation. Multimodality cannot be ruled out by a local Jacobian. Record all
flags. Rank-deficient/nonfinite covariance is unavailable, not a tiny ellipse.

## Prespecified scenarios and repetitions

- Four deterministic layouts: well-spread N13; elongated N7; a near-ring N6;
  the same near-ring with an additional high-precision near-core station, N7.
  Layout coordinates and scales are defined in the archived source and saved
  literally in each scenario's NPZ. No real station geometry is read.
- True directions (zenith, azimuth): (25,20) and (55,210) degrees.
- Chosen true core (120,-80,0) m; true A=200 ns at 1 km; time origin 100000 ns.
- Three regimes: independent calibrated Gaussian timing; the same noise plus
  deterministic asymmetric mean 30*rho*(d.e_theta)/10^6 ns; the same symmetric
  Gaussian measurements but reported sigma half the actual standard deviation.
- Actual station sigmas: 8+2*(index mod5) ns for well-spread; retained indices for
  elongated; ring (20,24,19,22,25,21) ns, added anchor 3.5 ns.
- 200 attempts per scenario: 24 scenarios, 4800 public fitter calls. Production
  default options, timing weighting, measured-data seeds (truth never seeded).
- Reproducible independent seed keys [202610131701, layout_index,
  direction_index, trial_index]. Noise is paired across regimes within a layout
  and direction; layout contrasts are not paired because dimensions differ.

The independent scalar generator does not call the fitted model or prediction
helper. Gaussian is a controlled hypothesis, not a detector-realism assertion.
Asymmetry and scale errors are deliberately imposed mismatches, not data-inferred
properties. No uncertainty method is tuned after inspecting measured coverage.

## Reporting and provenance

Primary per-scenario results: number attempted, optimizer success, covariance
availability, boundary count, delivered-and-covered fraction among all attempts,
coverage among available fits, and separately coverage among available interior
fits. An unavailable ellipse contributes zero to delivered-and-covered fraction
but is explicitly reported as unavailable; it is not described as an observed
failure of an ellipse that never existed. Also record angular error, ellipse
axes, covariance, fit vector, curvature, nominal reduced chi-square, all optimizer
attempt diagnostics, raw times, sigmas, geometry and true vector.

Two-sided 95% Wilson intervals quantify finite Monte Carlo sampling uncertainty
for each scenario. They are not simultaneous multiple-comparison guarantees and
do not imply generalization to real showers. 200 trials is intentionally bounded;
95% coverage estimates have limited resolution. All scenarios, including adverse
results, stay in the report. No chi-square-based deletions or uncertainty inflation.

Configuration, this protocol, production sources and experiment source are copied
and hashed before the production loop. Smoke runs use separate output paths and
are excluded from results. Each completed run emits checksummed artifacts. The
Stage B helper interface can be reused, but Stage A coverage outcomes must not be
used to tune Stage B validation thresholds.

## Exact / numerical checks required before production

Orthonormal tangent basis; analytic timing Jacobian against independent centered
finite differences on the sphere; full SVD covariance against an independently
computed nuisance-projected information matrix; correct uncertainty scaling;
rank-deficiency refusal; curvature-boundary flag; spherical log-map near zero and
azimuth seam; Wilson edge cases; invalid finite/shape/sigma inputs; known noiseless
direction inside its region. These validate implementation, not coverage itself.

## Reproduction

From repository root with project environment and single BLAS/OpenMP threads:

    python -m auger_reco.evaluation.direction_uncertainty --output NEW_PATH --trials 200

The output directory must not exist. Use a fresh path for every rerun.
