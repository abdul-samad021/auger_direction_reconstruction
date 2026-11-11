# Conference research conclusion — 13 October 2026

## Central result

**A curvature-aware timing model substantially improves timing predictions in
this training sample, but a small timing chi-square is not sufficient evidence
of a stable or accurate reconstructed direction.** Sparse geometry, loss of a
high-information station, uncertainty calibration and assumed core position all
matter. This project provides a reproducible investigation of those limitations,
not a claim to have surpassed the observatory's direction reconstruction.

The conference research package is
`reports/results/conference_validation_20261013_v1/`. Its final release receipt,
claim ledger, source snapshots and file hashes identify the evidence to use.
No historical results are replaced, and no Git commit or push is part of this
release. The protected 145 validation and 144 test events remain unopened.

## Question, model and interpretation

Can adding physically motivated curvature improve station-time prediction,
and under what conditions does that improvement fail to establish directional
reliability? A second question is how timing-uncertainty weighting behaves when
its assumptions are correct versus deliberately misspecified.

With station position $\mathbf r_i$, fixed core $\mathbf r_c$, downward unit
propagation vector $\mathbf u=-\mathbf s$, and perpendicular axis distance
$\rho_i=\| (\mathbf r_i-\mathbf r_c)\times\mathbf u\|$, our quadratic model is

$$
\widehat t_i=t_c+\frac{(\mathbf r_i-\mathbf r_c)\cdot\mathbf u}{c}
 +A\left(\frac{\rho_i}{1000\ \mathrm m}\right)^2,
\qquad A\ge0,
$$

$$
e_i=t_i-\widehat t_i,\qquad
\chi^2=\sum_i\left(\frac{e_i}{\sigma_i}\right)^2.
$$

$A$ is the curvature delay at 1 km, in ns. The plane model fixes $A=0$.
Timing-weighted fitting uses $\sigma_i=dt_i$; uniform fitting minimizes raw
squared timing errors. We report nominal reduced chi-square using $N-3$ or
$N-4$, but boundaries, nonlinear weak identification and model mismatch prevent
automatic interpretation as a calibrated significance test. Uniform-fit timing
chi-square is a diagnostic, not the objective that uniform fitting minimizes.

The real-data quadratic model uses **Auger's published core**, and all real-data
fits inherit its released selected stations and calibrated timing measurements.
Published direction is reserved for subsequent comparison, but that does not
make the core-assisted pipeline fully independent. Fixed-core leave-one-out
(LOO) predicts an omitted station conditional on a core obtained using the full
event. It is not end-to-end independent cross-validation.

## Established training-cohort result, independently re-audited

711 training events, four model/weighting combinations and all requested
station-omission fits were already complete. The new audit independently
recalculates predictions, objectives and reference angles rather than trusting
printed notebook output. There are 2,844 successful full-event fits. Among
25,392 requested full/LOO fits, 22,452 succeed and 2,940 fail the documented
minimum-station rule: 245 six-station events times six omissions times two
quadratic weightings. These are structural exclusions, not silent solver losses.

Timing-weighted comparisons:

| Metric | Common events | Plane median | Quadratic median | Median paired difference, quadratic minus plane [95% bootstrap interval] |
|---|---:|---:|---:|---:|
| Nominal reduced chi-square | 711 | 26.9693 | 1.5256 | -24.7218 [-25.8680, -23.3681] |
| In-sample timing RMS (ns) | 711 | 308.9849 | 71.8792 | -212.6781 [-229.6354, -201.4604] |
| Separation from Auger reference (deg) | 711 | 1.1060 | 0.3066 | -0.7882 [-0.8699, -0.6952] |
| Conditional held-out timing RMS (ns) | 466 | 366.3354 | 123.9812 | -221.3886 [-234.5348, -209.3494] |
| Conditional held-out normalized MSE | 466 | 55.7004 | 5.9953 | -44.5806 [-46.2231, -41.8766] |
| Maximum conditional LOO direction shift (deg) | 466 | 1.8223 | 0.5488 | -0.9709 [-1.0593, -0.8684] |

Each event has equal weight. Intervals use 2,000 paired event-bootstrap resamples
with seed 2026101309. They describe variation under empirical resampling of this
already-observed, selected training population. They are neither blinded
generalization intervals nor estimates of true pointing accuracy. The paired
median difference is intentionally **not** the difference of marginal medians.

Adverse cases remain in the result: quadratic reference agreement worsens for
61/711 events; conditional held-out RMS worsens for 14/466; normalized held-out
MSE worsens for 27/466. Furthermore, 131/466 quadratic fits change direction by
more than one degree after at least one station is omitted. The one-degree
threshold is descriptive, not an approved rejection rule. The quadratic
nominal reduced chi-square exceeds five for 114/711 events.

The focus event remains an illustrative counterexample outside this population:
nominal reduced chi-square improves 72.93 to 4.65, but separation from Auger
worsens 0.264 to 0.552 degrees. We retain both results rather than selecting only
events with improved reference agreement.

## New coordinate audit

The original official tutorial archive was retrieved and its SHA-256 matches
the previously examined source. Its approximate site-to-UTM/altitude map
contains an Earth-curvature-related altitude term. Checks against 712 published
cores and 1,533 unique station-position records support keeping site z distinct
from altitude minus 1400 m. No blanket extra correction is scientifically
justified. Applying a deliberately incorrect extra altitude term can move a
direction while barely changing chi-square; that counterfactual is **not** an
uncertainty bound or a proposed correction.

32 exact plane/quadratic refits test translations, rotations, timing sign and
cardinal directions. Remaining limitations include the precise exporter/datum,
a latitude comment discrepancy, and a small set of station/map outliers. The
largest station-map altitude discrepancy is 13.94 m; its cause is unresolved.
Those outlier IDs occur in neither the focus nor extreme-instability event.
See `docs/conference_coordinate_audit.md` for every denominator and caveat.

## New investigation of the extreme direction shifts

Six targeted training cases were selected by frozen rules: largest archived
LOO influences, high-chi-square cases and a multiplicity-matched stable control.
This is an explanatory case study, not a prevalence estimate.

Stronger solver settings and an independent variable-projection implementation
reproduce the public fitter's best objectives. The latter solves reference time
and nonnegative curvature analytically at each trial direction. Agreement across
these implementations provides no evidence that a lower competing objective was
missed in the examined cases; it is not a global-optimum proof for every event.

The three strongest instability examples have seven stations. Their omitted
near-core station carries approximately 62%, 75% or 80% of the inverse-variance
weight and local leverage close to one. Their full-fit residual can nevertheless
be small: an influential datum strongly controls the fitted surface. Removing
it allows much larger curvature and direction shifts of 18.58, 16.95 and
12.88 degrees. These stations have saturation flag 2, but that association does
not establish that the timing measurement is corrupted.

Core-offset scans also change direction; an apparently good timing fit does not
remove core dependence. The scans are fixed sensitivity scenarios, not posterior
core uncertainties. In a simplified flat quadratic surface, shifting the core
can be absorbed into intercept and linear slopes. The full 3D constrained model
does not inherit that exact identity in all cases, but can remain weakly
identified. Full diagnostics and distinctions are in
`reports/conference_instability_conclusion.md`.

### Post-hoc, known-truth anchor-removal check

After observing the mechanism, a separately frozen follow-up used those three
geometries and the stable control. It used a chosen synthetic direction
(30,45) degrees, chosen core, 200 ns curvature delay at 1 km and calibrated
Gaussian noise. There were 200 paired draws per geometry and 1,600 successful
full/omitted fits. Real event directions were not treated as simulated truth.

Omitting the preselected station increased median paired true angular error in
all four layouts. In the most severe layout, median angular error rose from
0.790 to 1.982 degrees, the 95th percentile from 2.003 to 24.795 degrees, and
the fraction above one degree from 35.5% to 82.5%. Mean nominal reduced
chi-square after omission was still **0.961**. Its median paired error increase
was 1.150 degrees [0.909, 1.413] under paired Monte Carlo bootstrap resampling.

No corrupted timing was injected. This demonstrates that information loss in
the chosen geometry is sufficient to produce poor direction recovery despite
apparently acceptable average chi-square. The stable control also deteriorated,
and not every extreme real-event geometry developed a similarly heavy tail.
It is not a validated classifier for bad or saturated stations.

## New bounded front/noise mismatch study

The final stress run uses 72 fixed scenarios: three layouts, two station counts,
two true directions, six front/noise regimes and 100 paired draws per scenario.
That is 7,200 synthetic datasets, 28,800 noisy fits and 96 noiseless controls.
The generators distinguish asymmetric mean arrival surfaces, radial actual
variance, incorrectly reported uncertainty, heavy tails and centered skew.
All methods see the same data within a paired trial; the quadratic receives the
known synthetic core. No fitted direction is initialized using truth.

All 28,800 noisy fits succeeded; 72 matching-model exact controls passed and
24 additional plane-on-curved controls deliberately tested mismatch. There were
zero violations in 14,400 nested-objective checks. An independent implementation
recomputed every noisy prediction, objective and angular error from saved
parameters. Curvature-boundary diagnostics (48 fits) were retained.

Across the twelve fixed geometry/count/direction scenarios, the median of the
scenario-median timing-quadratic angular errors was 0.2174 degrees for matched
Gaussian curvature and 0.7797 degrees with an asymmetric mean front. Curvature
helped paired true-direction errors in 10/12 asymmetric scenarios, but worsened
two; timing weighting helped the quadratic fit in five and worsened it in seven.
These adverse outcomes are part of the conclusion, not excluded failures.

Holding the actual noisy observations identical but underreporting uncertainties
in a distance-dependent way changed the quadratic angular summary from 0.4499
to 0.5832 degrees and its nominal chi-square summary from 0.9869 to 4.6003.
The angular statistic is a median of twelve scenario medians; the chi-square
statistic is a median of twelve scenario means. Neither is a real-detector
angular resolution. Uniform-fit angles stay identical in this paired check.

These are controlled mathematical stress models, not calibrated air-shower plus
detector simulation. Neither a random detector population nor all physical
effects are represented. See `reports/conference_stress_conclusion.md` for the
final verified metrics, adverse scenarios, failure counts and confidence
intervals. A successful method under matched Gaussian curvature is not presumed
best under an asymmetric mean or incorrect weights.

## Remedy decision and independent core/signal work

We retain the existing plane baseline and explicitly core-assisted quadratic
experiment. No new station-rejection policy, arbitrary uncertainty inflation,
curvature cap or ML correction is promoted merely to push chi-square toward
one. The numerical investigation does not justify an optimizer patch; the
identified loss of information cannot be repaired by convergence tolerance alone.

The earlier independent horizontal signal-core experiment is also retained as a
negative/mixed result: only 6/20 development events improved conditional held-out
normalized timing MSE, and some signal/core fits reached implausible boundaries.
That prototype still fixed published core altitude, used a simplified signal
objective and lacked a calibrated joint detector likelihood. It is not promoted
as fully independent or generally better reconstruction.

Justified next research is calibrated core/signal information, uncertainty
propagation and independently evaluated stability rules; then protected-data
evaluation under a frozen procedure. Neural correction and detector-level
simulation remain future research, not completed conference achievements.

## Contribution and limitations

Curved shower-front fitting, timing weights and signal/core reconstruction are
established methods. Our contribution is their transparent reimplementation and
paired assessment on this release, the preservation of adverse cases, and the
focused numerical/geometry investigation showing why timing fit quality and
directional reliability are different questions. No literature-priority or
new-fundamental-physics claim is made.

The official reconstruction paper describes parabolic and expanding-sphere front
models, timing uncertainty and signal/core estimation; our fixed-core timing
experiment is not a reproduction of the entire official chain.
[Pierre Auger Collaboration, JINST 15 (2020) P10021](https://arxiv.org/html/2007.09035v4).
Released timing, selection and saturation-field semantics are documented in the
[Auger Open Data field documentation](https://opendata.auger.org/data.php).

The conference statement is therefore: **curvature improves conditional timing
prediction substantially, while controlled and real-data diagnostics expose
important limits to directional robustness.** Completion of this conference
investigation does not mean the full research/deployment roadmap is finished.
