# Broadened Gaussian timing-noise benchmark

Run directory: `synthetic_plane_benchmark_20261010T104612_802216Z`.

The study used 432 predeclared scenarios and 200 paired trials per scenario: 86,400 noisy synthetic events and 172,800 fits. There were 18 geometry-family/count/layout combinations derived from nine base random layouts. Both methods received identical observations within each pair.

All recorded equal-uncertainty and objective-order controls passed. The full control results are in `control_checks.json`.

Timing-fit failures: 0; uniform-fit failures: 0; incomplete pairs: 0.

## Descriptive balanced-grid comparison

| Uncertainty profile | Complete / requested pairs | Timing wins | Uniform wins | Ties | Median of scenario median improvements (deg) |
|---|---:|---:|---:|---:|---:|
| equal | 43,200 / 43,200 | 0.00% | 0.00% | 100.00% | -0.000000 |
| heterogeneous | 43,200 / 43,200 | 65.12% | 34.87% | 0.01% | 0.025605 |

Win fractions are conditional on complete pairs. These pooled percentages are descriptive, not a population estimate; failures can alter scenario weights. The last column gives equal weight to each available scenario median.

Among 216 heterogeneous-uncertainty scenarios, 216 had positive median paired improvement beyond the numerical tie tolerance, 0 had negative improvement, 0 were within tolerance, and 0 were unavailable. Positive improvement means the uniform error minus the timing-weighted error is positive.

## Timing-model diagnostics

- equal, Timing-weighted: mean of scenario mean reduced chi-square = 1.0000.
- equal, Uniform: mean of scenario mean reduced chi-square = 1.0000.
- heterogeneous, Timing-weighted: mean of scenario mean reduced chi-square = 0.9994.
- heterogeneous, Uniform: mean of scenario mean reduced chi-square = 1.3641.

These are equal-scenario averages over successful fits. Weighted reduced chi-square is expected approximately near one under the correct Gaussian plane model. Uniform-fit chi-square remains an uncertainty-standardized diagnostic, not the uniform optimization objective.

Across 1,209,600 generated station errors, noise divided by its stated standard deviation had mean 0.00039 and standard deviation 1.00069. These are injected errors, not post-fit residuals.

## Interpretation and limits

The experiment tests uncertainty weighting under a known, correctly specified plane-front model. Weighting need not win on every noise realization or every finite-sample scenario. The equal-uncertainty condition is a numerical control.

Per-scenario paired-median bootstrap intervals are conditional Monte Carlo uncertainties, not uncertainties about arbitrary real detector arrays. They are exploratory and not multiplicity-adjusted. Each p95 estimate uses only roughly ten upper-tail trials and should not support precise rankings.

Flat arrays, correctly calibrated independent Gaussian errors, matched RMS extent, three base layouts per count, and the selected directions limit generalization. Station-count layouts are not nested. Curvature, terrain, correlated errors, outliers, and misestimated uncertainties were not tested. No claim of improved real-Auger reconstruction or reduced real-event chi-square follows from this study.

## Next physics experiment

Introduce controlled shower-front curvature with known synthetic truth, evaluate the plane-model mismatch, and implement/test a curvature-aware fitter before returning to the real-event comparison.
