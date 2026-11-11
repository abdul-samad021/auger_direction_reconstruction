# Conference study: station influence, core dependence and directional stability

**Status:** completed training-only diagnostic study, 2026-10-13. No baseline
fitter, original result, official station selection or uncertainty was changed.
No validation/test event was accessed. No commit or push was performed.

Primary artifacts: reports/results/conference_validation_20261013_v1/instability/.
The primary frozen protocol and source copies are in its source_snapshot/;
the clearly separated post-hoc mechanism experiment is in anchor_ablation/.
The current protocol and runner include that later addition; the original
snapshots preserve exactly what was run for each stage.

## Main result

The largest archived leave-one-out direction changes are reproducible with
tighter public-fit tolerances and an independent variable-projection solver.
The evidence does **not** identify an optimizer fix that would remove them.
Instead, the three most unstable seven-station cases depend strongly on one
near-core, high-weight station that constrains time and curvature. Omitting
that station permits very different directions and much larger fitted
curvature. Their small full-fit residuals do not identify this vulnerability.

A separate, explicitly post-hoc known-truth simulation on those layouts
demonstrates that removing the preselected station can degrade angular
reconstruction even when the generator matches the fitter and the Gaussian
uncertainties are correct. No saturation-related timing error was injected.
This supports an information/geometry-loss mechanism, not a claim that the
released saturated station times are faulty.

## 1. Frozen selection and computation

Six unique cases were selected from the already inspected 711 training events:

| Event ID | Reason | Stations | Full nominal reduced chi-square | Maximum archived LOO shift |
|---|---|---:|---:|---:|
| 081881294400 | Largest influence | 7 | 2.6676 | 18.5778 deg |
| 133035602401 | Second-largest influence | 7 | 0.6068 | 16.9486 deg |
| 140415557800 | Third-largest influence | 7 | 0.3778 | 12.8812 deg |
| 082726270900 | Median stable seven-station control | 7 | 0.2916 | 0.5110 deg |
| 113434887000 | High chi-square, complete LOO | 7 | 43.1823 | 3.7223 deg |
| 143024870400 | High chi-square, complete LOO | 8 | 49.2396 | 4.1121 deg |

The targeted selection does not estimate population prevalence. Prevalence
statements must come from the complete training analysis, not these six cases.

For each event both the full set and its archived largest-influence omission
were examined:

- 24 public fits at the original and stronger settings.
- 168 independent profiled-direction optimizer calls (14 starts per context).
- 108 public fixed-core-offset sensitivity fits (9 offsets per context).
- 1,212 analytic conditional objective-profile points.
- 1,706 internal public-fitter optimizer attempts, all accepted; all 168
  independent profiled-direction calls also reported success.
- Selected-station signal, uncertainty, saturation, position, residual and local
  leverage tables, joined by station ID.

Full and omitted directions were not constrained to agree with Auger's
published direction. New direction-reference comparisons were not needed.

## 2. Numerical reproduction and alternative starts

The unchanged default fitter exactly reproduced the archived objectives and
directions in all 12 full/omitted contexts. Strong settings used tolerances
1e-12, up to 10,000 evaluations, and positive curvature seeds of 1, 25, 100,
500 and 2,500 ns at 1 km.

The independent solver eliminates core time and nonnegative curvature
analytically at each direction, then optimizes only two sky slopes. It uses
cross-product transverse distances, centered timestamps and three-point
numerical derivatives rather than the public solver's four-parameter
analytical-Jacobian formulation.

- Largest improvement of the independent best objective over the default:
  **5.79e-11**, numerically immaterial here.
- Largest stronger-fit change from its archived direction:
  **2.15e-5 deg**, far below the 12.9–18.6 deg omission effects.
- Recomputing profiled objectives at public fitted directions agreed within
  **1.43e-12** in objective.
- Independent central differences agreed with the analytical six-parameter
  diagnostic Jacobian to a maximum scaled error of **5.19e-10**.

The three unstable omitted-station contexts also admitted higher-objective
local or boundary solutions from some starts. For event 081881294400, the
best branch has objective 2.73755 and A=2463.05 ns at 1 km; a zero-curvature
branch has objective 7.51675. For 140415557800 the corresponding objectives
are 0.61764 and 1.08789. Event 133035602401 has curved branches at objectives
0.38886 and 0.68903. The public multi-start fitter selected the lowest branch
found independently. Agreement among these starts is not a mathematical
proof of global optimality.

## 3. Physical station information and the near-core anchor

| Event | Omitted station | Fitted axis distance | Timing-weight share | Local leverage | Full standardized residual | A: full -> omitted |
|---|---:|---:|---:|---:|---:|---:|
| 081881294400 | 957 | 216 m | 62.0% | 0.999470 | -0.00850 | 183 -> 2463 ns |
| 133035602401 | 941 | 148 m | 75.3% | 0.999922 | +0.01125 | 260 -> 3526 ns |
| 140415557800 | 923 | 261 m | 80.0% | 0.999966 | -0.00105 | 259 -> 1715 ns |

All three carry released sat=2. The official field table defines this as
both high- and low-gain saturation. It does **not** label the station timing
invalid. The timing adapter does not remove stations by saturation; the
experimental signal model separately treats such amplitudes cautiously.
[Auger Open Data field semantics](https://opendata.auger.org/data.php)

Signal sizes are respectively 21077, 26917 and 2211 VEM, and released timing
uncertainties 17.84, 18.39 and 18.53 ns. These are physical metadata, not
grounds to alter the uncertainties or reject the stations.

After the near-core anchor is omitted, remaining full-fit axis distances are
approximately 1238–1687 m, 1337–1608 m and 1261–1744 m. Those comparatively
ring-like samples lose a central constraint on the separation of core time,
curvature and direction. In contrast, the stable control's remaining radii
span 595–1976 m and its curvature barely changes (187 -> 184 ns at 1 km).
This is a case-based mechanism inference, not a universal geometric classifier.

The local leverage is the diagonal of the linearized weighted projection
matrix for four fixed-core parameters. Values near one mean that a point
strongly determines its own fitted value; a tiny residual can coexist with
large deletion influence. It is not a causal detector-fault probability.

For the high-chi-square cases, the most influential omitted stations have
much smaller timing-weight shares (2.44% and 2.59%) and full standardized
residuals of -3.96 and -5.46. Their omission still leaves nominal reduced
chi-square 25.21 and 31.50. Removing one station therefore does not explain
away those events' timing-model mismatch.

## 4. Local identifiability and direction profiles

The column-normalized fixed-core Jacobian condition numbers changed as follows:

| Event | Full | Worst omission |
|---|---:|---:|
| 081881294400 | 2.20 | 54.73 |
| 133035602401 | 2.52 | 127.44 |
| 140415557800 | 1.99 | 64.72 |
| Matched stable 082726270900 | 3.94 | 4.02 |

Full-fit condition numbers alone did not reveal the omission vulnerability:
the stable control even has the largest full condition number among these
four. Explicit deletion checks supply information that a convergence flag
or a single local full-fit diagnostic does not.

The objective profiles refit core time and curvature at every direction
along the shortest spherical arc from the full to the omitted solution.
For event 081881294400, the omitted data admit objective 8.0003 at the
full-fit direction and 2.7375 at the direction 18.58 deg away. Restoring
station 957 increases the profiled objective at that displaced direction
to 2144.26, compared with 8.0029 at the full optimum. The anchor is therefore
informative, not merely an obvious large-residual outlier.

These are descriptive conditional objectives. The report does not infer
confidence regions or p-values from their differences.

## 5. Core sensitivity and what can actually be identified

Fixed ±50 and ±100 m x/y offsets, with z unchanged, produced full-fit direction
changes up to **0.60–0.89 deg** across the six cases. Their full-fit nominal
reduced chi-squares changed comparatively little. For example, 081881294400
spans 2.592–2.744 while direction changes reach 0.630 deg.

The same probes on already unstable omitted sets can trigger much larger
branch/direction changes: maxima **20.09, 15.40 and 15.24 deg** for the three
top-influence cases. The stable control remains below 0.577 deg. These offsets
are deliberately fixed sensitivity scenarios, not measured core-error draws
or calibrated confidence intervals. The unchanged public multi-start fitter
was used for every offset; a global optimum is not proved by this grid.

Adding core-x/y derivative columns raises the normalized local condition
number into the hundreds or thousands. This diagnoses coupling; it is not
an independent fitted core or an uncertainty estimate.

The simplified one-dimensional timing model illustrates the coupling:

$$
t(x)=a+bx+k(x-x_c)^2
    =(a+kx_c^2)+(b-2kx_c)x+kx^2.
$$

In that toy model, a shifted core can be exactly compensated by changes to
time and linear timing slope. In our three-dimensional unit-vector model,
transverse distance itself changes with direction; the full relationship is
not this exact algebraic degeneracy. The reported Jacobians and profiles
instead demonstrate case-dependent near-degeneracy and sensitivity. We must
not claim that all real-event timing fits have an exact free-core symmetry.

## 6. Separate post-hoc known-truth anchor-ablation experiment

The hypothesis above was followed by an approved, separately frozen experiment
using the three unstable layouts and the matched stable layout. We generated
quadratic timings at chosen zenith 30 deg, azimuth 45 deg, A=200 ns at 1 km,
with Gaussian noise scaled by the released station dt. The published core
coordinates were used as chosen **synthetic generator cores**, not real truth.
The previously selected station was removed in each paired reconstruction;
no detector fault or saturation-dependent error was injected.

Exactly 200 paired draws per layout gave **800 synthetic datasets and 1600
successful fits**, with all 9138 internal public optimizer starts accepted.
The seed was 20261013. The 1-degree error threshold and 2000 paired bootstrap
resamples were fixed before the simulation. No fitting parameters were tuned
from these results.

| Layout | Median true error, full -> omitted | Median paired increase [95% bootstrap] | Fraction error >1 deg, full -> omitted |
|---|---:|---:|---:|
| 081881294400 | 0.495 -> 0.833 deg | 0.329 [0.247, 0.408] deg | 7.0% -> 36.0% |
| Stable control 082726270900 | 0.401 -> 0.643 deg | 0.181 [0.109, 0.269] deg | 5.5% -> 22.0% |
| 133035602401 | 0.800 -> 1.209 deg | 0.368 [0.229, 0.506] deg | 33.5% -> 61.5% |
| 140415557800 | 0.790 -> 1.982 deg | 1.150 [0.909, 1.413] deg | 35.5% -> 82.5% |

Median paired increase means median(error_omitted - error_full), not the
difference of the two marginal medians. Bootstrap intervals describe the
finite paired toy sample; they are not calibration intervals for real data.

The fourth layout has omitted p95 true angular error **24.795 deg** despite a
mean nominal reduced chi-square of **0.961**. The largest error is 33.199 deg.
A post-hoc independent numerical audit of the worst omitted draw in each
layout, including the true direction as one audit start, recovered the same
best objectives to 3.4e-12 or better. The 33.199-degree solution therefore was
not eliminated by simply improving the starting point. All 56 audit starts
converged; these diagnostics did not alter the 1600 original results.

The stable control also worsens after station removal. The first and third
unstable layouts do not reproduce the fourth layout's large tail at this
chosen direction. Therefore the result supports sensitivity to geometry,
information and direction; it does **not** establish a saturated-station
classifier, a generic 7-station failure rate, or a single cause of all
real-event residuals. Only one generated direction and curvature were used.

## 7. Remedy decision and conference claim

No optimizer correction, automatic station rejection, uncertainty inflation,
curvature cap or ML correction is promoted by this study. The existing
baseline is unchanged. The independent solver is an audit tool, not a newly
selected better reconstruction algorithm.

The justified immediate improvement is diagnostic reporting: retain local
leverage, omission sensitivity, core sensitivity, competing solutions and
curvature alongside nominal goodness-of-fit. A quantitatively calibrated
quality cut or curvature prior would require a new declared experiment and
appropriate independent validation. Large fitted A alone is not grounds for
an after-the-fact bound that forces agreement with Auger.

**Poster-ready statement:** In targeted seven-station training cases,
near-core high-leverage stations constrained curvature and direction despite
negligible timing residuals. Removing them produced 12.9–18.6-degree direction
changes that survived independent numerical checks. Known-truth paired
simulations demonstrated degraded angular accuracy after the same removals,
including a layout with 24.8-degree p95 error while mean nominal reduced
chi-square remained near one. These results motivate stability diagnostics
in addition to timing goodness-of-fit.

## Reproduction and tests

Use the archived source snapshot for the exact original primary run; with
current source, new runs require an unused run directory to avoid overwriting.
The runner provides --anchor-ablation and --audit-anchor-tails as separate
stages and refuses to overwrite their artifacts. All source and selected
input hashes are archived. All physical station rows and failed-attempt
structures are retained; no failed outcome was hidden (none occurred here).

tests/test_conference_instability.py covers independent quadratic algebra,
nonnegative-curvature profiling, timestamp translation, analytical/numerical
derivatives, exact recovery, multistart results, deterministic selection,
protected-design safeguards, receipt integrity, no-overwrite behavior,
paired bootstrap semantics and invalid input handling. At completion:
**29 tests passed with warnings treated as errors**, and the runner/tests
passed the configured formatting and lint checks.

Release integration subsequently added an explicit `--output` option, without
altering the fitting calculations, so the study can be reproduced in a fresh
directory. Two additional interface/no-overwrite tests bring this module's
current test count to 31; original run snapshots remain unchanged.

This remains a published-core-assisted analysis using official station
selection. Conditional LOO is not full independent event reconstruction.
The training-only, targeted study does not establish absolute angular
accuracy on measured showers or replace detector-level simulation.
