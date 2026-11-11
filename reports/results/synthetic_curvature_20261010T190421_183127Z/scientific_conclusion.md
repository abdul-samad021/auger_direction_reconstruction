# Controlled-curvature experiment: scientific conclusion

Run: synthetic_curvature_20261010T190421_183127Z

## Design

Sixteen fixed geometry/direction/core cases, five curvature levels, and 100 Gaussian-noise draws per case produced 8,000 paired synthetic datasets and 32,000 plane/quadratic, timing/uniform fit attempts. Four flat layouts were reused. The quadratic fitter was supplied the true core but not the true direction or curvature.

## Verification and failures

- 320 noiseless fits completed successfully. The matching-model subset passed exact-recovery gates; the symmetric-plane parity control also passed.
- Main failed or invalid fits: 0/32000.
- Stress-study failed or invalid fits: 0/1200.
- Nested-objective violations: 0.
- Detailed optimizer attempts and failed outcomes are retained; summaries of errors are conditional on successful fits.

## Main results

These values are **medians across the 16 case-specific median angular errors**, not a population angular resolution. Chi-square values are means of case means.

| A at 1 km (ns) | Plane median (deg) | Quadratic median (deg) | Plane nominal reduced chi-square | Quadratic nominal reduced chi-square |
|---:|---:|---:|---:|---:|
| 0 | 0.068358 | 0.076106 | 0.9959 | 1.0399 |
| 25 | 0.263781 | 0.081847 | 3.4994 | 1.0011 |
| 50 | 0.492048 | 0.081658 | 10.9650 | 1.0011 |
| 100 | 0.957538 | 0.080966 | 40.7821 | 1.0011 |
| 200 | 1.890178 | 0.079650 | 159.9603 | 1.0012 |

Among 64 positive-curvature, timing-weighted scenarios, 57 had a positive median paired angular improvement and 4 had a negative one beyond the 1e-05 degree numerical tie threshold. These are descriptive counts, not multiple-testing-adjusted significance claims. Per-scenario paired bootstrap intervals are in paired_summary.csv.

At zero injected curvature, the mean boundary-fit fraction was 0.482 using A <= 0.001 ns. Noise can produce positive fitted curvature even for planar data. The nominal N−4 denominator is not an exact boundary-law calibration.

The symmetric, centred noiseless control retains direction accuracy while accumulating timing mismatch. Therefore, residual disagreement and directional accuracy must be reported separately.

## Core and model-mismatch sensitivity

| Condition | Plane median error (deg) | Quadratic median error (deg) | Quadratic nominal reduced chi-square |
|---|---:|---:|---:|
| quadratic_correct_core | 1.997728 | 0.073034 | 1.0011 |
| quadratic_core_x_plus_100m | 1.997728 | 0.323222 | 1.0053 |
| quadratic_core_x_minus_100m | 1.997728 | 0.333606 | 1.0021 |
| quadratic_core_y_plus_100m | 1.997728 | 0.226551 | 1.0015 |
| quadratic_core_y_minus_100m | 1.997728 | 0.224386 | 1.0033 |
| spherical_cap_correct_core | 2.004168 | 0.073448 | 1.0008 |

The translating-cap generator differed from the quadratic timing model by at most 1.1188 ns in the preselected example. This is one limited shape-mismatch test, not a full shower simulation. Core shifts of 100 m are sensitivity probes, not a claimed Auger uncertainty distribution.

## Limitations and next requirements

- The known-core assumption is an information advantage; independent core estimation and propagation of core uncertainty remain required.
- Geometry and direction coverage is deliberately limited. The 100 draws per scenario leave p95 exploratory. The bootstrap reflects timing-noise sampling conditional on fixed cases, not realistic shower-to-shower uncertainty.
- Gaussian independent noise with correctly specified uncertainties omits correlated timing, detector response, shower fluctuations, outliers and station selection.
- No true-direction-dependent distance entered either optimization. Truth-derived distances appear only in generation, checks, and explicitly labelled diagnostic plots.
- Do not call this a reduction of the measured event's chi-square or an improvement over Auger. Those real-data comparisons have not been performed here.
- Preserve the plane baseline; validate the core strategy and additional failure modes before real-event curvature reconstruction and a frozen cohort study.

Physics reference: [Auger, JINST 15 (2020) P10021, Section 5.1](https://arxiv.org/pdf/2007.09035). The paraboloidal timing form is adapted; the complete Auger reconstruction is not reproduced.
