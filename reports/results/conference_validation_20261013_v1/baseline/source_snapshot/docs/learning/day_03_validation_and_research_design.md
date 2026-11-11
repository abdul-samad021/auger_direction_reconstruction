# Day 3 — Diagnostics, validation, and the research design

## Purpose

A numerical optimizer can always return numbers when it is given enough valid
inputs. That does not establish that the numbers describe the event well. This
module defines how we will test the reconstruction, identify its failure modes,
compare it fairly with Auger's reference reconstruction, and decide whether a
machine-learning correction adds scientific value.

The central research question is:

> How accurately can we reconstruct the arrival direction of a cosmic-ray air
> shower using only Pierre Auger surface-detector positions, timing measurements,
> and uncertainties—and can a carefully validated machine-learning correction
> improve upon the physics-based reconstruction?

The project therefore has two linked scientific claims to test:

1. A transparent plane-front model can independently recover useful direction
   information from station geometry and timing.
2. A leakage-controlled correction model may improve the remaining angular error
   on events that were not used to develop it.

Machine learning does not replace the physics. The physics model establishes what
is predicted, what assumptions were made, and what errors remain for a correction
model to learn.

## 1. Station-level residuals

For station $i$, define

$$
\boxed{
e_i=t_i^{\mathrm{obs}}-t_i^{\mathrm{pred}}
}.
$$

The sign is always interpreted using “observed minus predicted”:

- $e_i>0$: observed later than predicted;
- $e_i<0$: observed earlier than predicted;
- $e_i\approx0$: close timing agreement.

If a station is observed $18$ ns later than predicted,

$$
\boxed{e_i=+18\ \mathrm{ns}}.
$$

With $dt_i=6$ ns, its standardized residual is

$$
\boxed{
q_i=\frac{e_i}{dt_i}=\frac{18}{6}=+3
}.
$$

It was observed three stated uncertainties later than the model predicted.

As a rough diagnostic rather than a deletion rule:

- $|q_i|<1$: close agreement relative to the uncertainty;
- $|q_i|\approx2$: notable disagreement;
- $|q_i|\geq3$: a station or model behaviour worth investigating.

## 2. Event-level fit statistics

The weighted timing disagreement is

$$
\boxed{
\chi^2=\sum_{i=1}^{N}q_i^2
=\sum_{i=1}^{N}
\left(\frac{e_i}{dt_i}\right)^2
}.
$$

It should be accompanied by the number of degrees of freedom,

$$
\boxed{
\nu=N-k
},
$$

where $N$ is the number of fitted stations and $k$ is the number of fitted
parameters. Our constrained plane model estimates

$$
t_{\mathrm{ref}},\quad\theta,\quad\phi,
$$

so $k=3$. With 24 selected stations,

$$
\boxed{\nu=24-3=21}.
$$

The reduced chi-square is

$$
\boxed{
\chi^2_{\mathrm{red}}=\frac{\chi^2}{\nu}
}.
$$

Under a correct model with independent Gaussian errors and correctly calibrated
uncertainties:

- $\chi^2_{\mathrm{red}}\approx1$: residual size is broadly consistent with `dt`;
- $\chi^2_{\mathrm{red}}\gg1$: disagreement is larger than expected;
- $\chi^2_{\mathrm{red}}\ll1$: uncertainties may be too large, errors may be
  correlated, or the statistical model may otherwise be incomplete.

### What a large reduced chi-square does and does not prove

A large value does not by itself prove that the reconstructed direction is wrong.
It can also arise from:

- a curved front being approximated as a plane;
- underestimated timing uncertainties;
- one or more unusual station timings;
- correlated station errors;
- incorrect units or coordinate conventions;
- a poor optimization result.

It is also important to get the uncertainty direction right: a **larger** `dt`
makes $|q_i|=|e_i|/dt_i$ smaller for the same raw residual. Small stated
uncertainties make a disagreement more statistically significant.

Fit quality therefore requires both summary statistics and residual plots.

## 3. RMSE and MAE

Two useful unweighted timing summaries are

$$
\boxed{
\mathrm{RMSE}
=\sqrt{\frac{1}{N}\sum_i e_i^2}
}
$$

and

$$
\boxed{
\mathrm{MAE}
=\frac{1}{N}\sum_i|e_i|
}.
$$

Both remain in nanoseconds. RMSE penalizes large residuals more strongly, whereas
MAE is less dominated by an extreme station. They supplement chi-square but do not
replace it because they ignore the differences among station `dt` values.

## 4. Residual patterns and their physical meaning

A good reconstruction should have residuals that are not only small, but also free
of unexplained structure. We will inspect:

- residual versus station $x$;
- residual versus station $y$;
- residual versus predicted or relative time;
- standardized residual versus `dt`;
- standardized residual versus signal;
- residuals coloured over the detector footprint;
- a histogram or quantile plot of standardized residuals.

Typical patterns include:

| Residual pattern | Possible interpretation |
|---|---|
| Random scatter around zero | The plane may be an adequate baseline |
| Gradient across $x$ or $y$ | Direction or coordinate convention may be wrong |
| Curved, bowl-shaped spatial pattern | Shower-front curvature may remain |
| One isolated extreme residual | Influential station or unusual trigger |
| Dependence on signal | Timing behaviour may retain signal-dependent bias |
| Larger edge residuals | Curvature or sparse edge geometry may matter |
| Nearly all pulls much smaller than one | `dt` may be overestimated |

A curved or bowl-shaped residual map means stations in one spatial region are
systematically early or late relative to a flat plane. It is the residual pattern,
not a visibly curved reconstructed direction, that suggests front curvature.

## 5. Assumptions of the baseline model

### Plane-front approximation

We approximate the leading timing surface as a plane. A real extensive air shower
has curvature, finite thickness, stochastic particle arrivals, and a complicated
lateral distribution. The plane is a transparent baseline, not the complete
physics of an Auger reconstruction.

### Propagation speed

We assume the effective front propagates at approximately

$$
c=0.299792458\ \mathrm{m/ns}.
$$

### Independent timing errors

The diagonal weight matrix assumes different stations' timing measurement errors
are uncorrelated. Shared GPS, calibration, or atmospheric effects could violate
this assumption.

### Approximately Gaussian errors

The usual chi-square interpretation assumes that

$$
\epsilon_i\sim\mathcal N(0,dt_i^2).
$$

Strong tails or asymmetry in the standardized residual distribution would weaken
that interpretation.

### Calibrated `dt`

We assume each `dt` meaningfully describes uncertainty in the released start time.
Residual-versus-`dt` and residual-versus-signal plots help test this assumption.

### Valid station association

The first baseline fits only stations with `isSelected == 1`. Rejected triggers
remain visible in diagnostic plots but are not silently reintroduced into the fit.

### Correct units and conventions

Metres, nanoseconds, axis orientation, azimuth zero, angular rotation direction,
and the propagation-versus-sky sign must all be verified. A convention error can
produce neat plots and plausible-looking angles while still being physically wrong.

## 6. Limitations of the available comparison

### Auger's direction is a reference, not exact truth

The released Auger direction comes from a much more sophisticated reconstruction.
It is the best available evaluation reference, but it also has measurement and
model uncertainty. We will call it the **Auger reference reconstruction**, not the
perfect true direction.

### Azimuth becomes unstable near the zenith

For an exactly vertical event,

$$
u_x=u_y=0,
$$

so azimuth is undefined. Near vertical, a tiny horizontal-component change can
produce a large azimuth change even when the total 3D direction changes very little.

Angular separation between unit vectors is therefore safer than azimuth difference
alone:

$$
\Delta\psi
=\cos^{-1}
\left(
\mathbf a_{\mathrm{ours}}\cdot\mathbf a_{\mathrm{Auger}}
\right).
$$

### Sparse or one-sided geometry weakens reconstruction

Events with few selected stations, nearly collinear stations, or stations clustered
on one side of the footprint have weaker geometric leverage than events with many
well-distributed stations.

### The analysed population is selected

The public release and our eligibility rules do not represent every physical shower
equally. Conclusions must describe the population actually included in the study.

## 7. Numerical and geometric diagnostics

### Matrix rank

The design matrix must contain enough independent geometric information to estimate
the requested parameters. Rank deficiency means that some parameter combinations
cannot be distinguished.

### Condition number

A matrix can have full rank but still be nearly degenerate. A large condition number
means that small timing perturbations can produce large changes in the fitted
direction.

### Optimizer status and physical checks

Every result should record whether the optimizer converged, whether all returned
values are finite, whether the vector has unit length within tolerance, and whether
the downward sign is satisfied.

### Leave-one-station-out stability

Refit the event repeatedly while omitting one selected station at a time. If one
omission changes the direction dramatically, the reconstruction is fragile and the
influential station deserves investigation. This diagnostic does not automatically
authorize deleting the station.

### Alternative starting guesses

The constrained fit should be tested from its linear initial estimate and from a
small number of controlled alternative initial values. Strong dependence on the
starting point can reveal a poor local optimum.

## 8. Synthetic recovery before real-event interpretation

Before revealing any real event's Auger direction:

1. Use actual or simplified station coordinates.
2. Choose known values of $t_{\mathrm{ref}}$, $\theta$, and $\phi$.
3. Calculate exact plane-front arrival times.
4. Confirm exact recovery without noise.
5. Add controlled Gaussian timing noise based on plausible `dt` values.
6. Verify that recovered directions fluctuate sensibly around the known direction.
7. Test vertical, inclined, boundary-azimuth, and weak-geometry cases.
8. Intentionally introduce a sign or unit error and confirm that the diagnostics
   reveal it.

Synthetic data separate errors in our derivation or implementation from the
curvature and detector complications of a real shower.

## 9. Manual convention verification

Before comparing our angles with the withheld reference, record evidence for:

- the meanings and units of released `x`, `y`, and `z`;
- whether positive $z$ points upward;
- Auger's azimuth-zero direction;
- whether azimuth increases clockwise or counterclockwise;
- whether the published direction points along propagation or back toward the sky;
- the allowed zenith and azimuth ranges;
- at least one documented event or official transformation that tests the signs.

The conversion between our temporary mathematical convention and Auger's convention
should be isolated in one tested function. It must not be scattered through plots
and notebooks.

## 10. Data-leakage boundary

The direction reconstruction must be independent of Auger's released answer.

| Role | Examples | Allowed use |
|---|---|---|
| Baseline inputs | Selected `x`, `y`, `z`, `t`, `dt` | Fit the physical direction |
| Diagnostic-only station data | `signal`, `dsignal`, rejected triggers | Plots and later justified features |
| Evaluation references | Official zenith, azimuth, direction vector | Reveal only after prediction |
| Evaluation metadata | Official energy and quality fields | Stratified analysis after prediction |
| Prohibited baseline leakage | Official core, distances or fields derived from official reconstruction | Do not use to reconstruct the baseline |

Any candidate ML feature must have documented provenance. If it depends directly or
indirectly on Auger's reference direction, it cannot be presented as an independent
input.

## 11. Staged data progression

The first JSON event is a laboratory bench, not a research sample. The staged plan
is:

1. **Synthetic shower:** prove the mathematics and code recover a known answer.
2. **One real event:** freeze our prediction, reveal the reference, and understand
   every residual.
3. **Approximately 10–20 events:** expose parser, geometry, optimization, and
   convention failures.
4. **Frozen 1,000-event pilot:** measure distributions and develop the analysis
   without touching the final test answers unnecessarily.
5. **Justified larger sample or full eligible release:** run the stable pipeline
   when the scientific need is clear.

Code written for the first event must become a reusable function. We do not copy a
notebook cell separately for every JSON file.

## 12. Train, validation, and test discipline

Before training any correction model, split events into:

- training data for fitting model parameters;
- validation data or cross-validation folds for selecting features and
  hyperparameters;
- an untouched test set for the final comparison.

The test set remains untouched until the analysis procedure is frozen because
repeatedly changing the method after seeing test results indirectly trains the
researcher—and therefore the method—on the test set. That is test-set leakage even
when the test labels were never passed into the fitting function.

All candidate methods should be evaluated on the same test events. Event-by-event
paired error differences are more informative than averages from unrelated samples.

## 13. Multi-event evaluation metrics

For every event, record at least:

- angular separation from the Auger reference;
- number of selected stations;
- timing RMSE and MAE;
- $\chi^2$, degrees of freedom, and reduced $\chi^2$;
- matrix rank and condition number;
- convergence and failure status;
- leave-one-station-out sensitivity where practical.

Across events, report:

- median angular error;
- mean angular error for completeness;
- 68th-percentile angular error;
- 95th-percentile angular error;
- fraction of failed or invalid reconstructions;
- uncertainty intervals obtained by event-level resampling where appropriate.

Performance should also be shown in predeclared bins such as zenith and selected
station multiplicity. Evaluation-only metadata such as official energy may be used
for post-reconstruction stratification, not as a hidden baseline input.

## 14. Physics baselines before machine learning

The research comparison should establish progressively stronger baselines:

1. unweighted plane-front fit;
2. timing-uncertainty-weighted linear fit;
3. constrained unit-vector weighted fit;
4. robust or physically motivated correction, if justified by residual evidence;
5. physics baseline plus ML correction.

This ordering tells us whether an improvement comes from correct uncertainty
treatment, a physical constraint, outlier resistance, an explicit curvature model,
or machine learning.

If curvature is visible, a simple physical curvature model should be considered
before claiming that a complex model is required. The final comparison should be
fair rather than intentionally giving ML a weak baseline.

## 15. The role of machine learning

The scientifically meaningful ML task is to learn a correction to understood
baseline errors. Possible safe inputs, after provenance review, include:

- the baseline propagation or sky vector;
- summaries of raw and standardized timing residuals;
- selected-station multiplicity;
- detector-geometry summaries;
- signal-distribution summaries;
- rank, condition, and fit-quality diagnostics.

The target describes the difference between the baseline direction and the Auger
reference direction. It should be represented in a way that respects spherical
geometry—for example, as a correction vector rather than an unwrapped scalar
azimuth difference.

ML succeeds only if it improves untouched-test angular error, remains stable across
important event groups, and does not depend on leaked reference-derived fields.

Failure to improve is still a scientific result. It can show that the features do
not contain the missing information, that a physical model is preferable, or that
the remaining error is not learnable from the available release.

### Why SMOTE is not the default

SMOTE creates synthetic minority-class samples for classification. Our primary task
is continuous directional correction, not class prediction. Interpolating arbitrary
events could create geometrically or physically inconsistent synthetic showers.

If some parts of the event population are sparse, prefer:

- stratified sampling;
- sample weighting;
- balanced evaluation bins;
- grouped or stratified cross-validation;
- explicit reporting of weakly represented regions.

## 16. Robustness without silent data manipulation

Potential robustness methods include Huber or soft-$L_1$ losses, station-influence
analysis, and explicitly justified timing-quality rules. They should be compared
with the same event splits and reported as separate methods.

We must not repeatedly remove stations merely because doing so moves the result
closer to Auger's answer. That would tune the reconstruction against the evaluation
target and conceal genuine failure modes.

## 17. What makes the project significant

The project does not claim to invent cosmic-ray direction reconstruction or surpass
the Pierre Auger Collaboration's full internal analysis. Its undergraduate research
value comes from independently demonstrating that we can:

- derive and implement a physical timing model;
- work with authentic detector measurements and uncertainty;
- preserve a strict input/evaluation boundary;
- validate code on known synthetic cases;
- quantify performance over a reproducible event cohort;
- investigate model assumptions and failure modes;
- test whether ML provides a real held-out improvement;
- communicate results through documented software, plots, and a scientific report.

That combination provides defensible evidence of physics understanding, scientific
computing, statistics, machine learning, and software engineering.

## 18. Phase 1 scientific completion checklist

- [ ] Verify Auger's coordinate, zenith, and azimuth conventions.
- [ ] Recover known directions from exact and noisy synthetic showers.
- [ ] Implement unweighted, weighted, and constrained plane fits.
- [ ] Fit the first real event without reading its reference direction.
- [ ] Reveal the reference and calculate angular separation.
- [ ] Produce measured-versus-predicted and residual diagnostic plots.
- [ ] Convert the notebook experiment into reusable tested code.
- [ ] Diagnose approximately 10–20 varied real events.
- [ ] Run the stable pipeline on the frozen 1,000-event pilot.
- [ ] Report angular-error distributions and failure rates.
- [ ] Examine performance versus zenith, geometry, and multiplicity.
- [ ] Test a justified robust or physical curvature improvement.
- [ ] Train a leakage-controlled ML correction only after baselines are frozen.
- [ ] Compare every method on the same untouched test events.
- [ ] Report uncertainty, limitations, negative results, and failure cases.
- [ ] Produce final figures, tables, reproducible instructions, and report.

Only after these scientific questions have been answered does Phase 2 begin: API,
interface, Docker packaging, cloud deployment, monitoring, and other product-level
software work.

## 19. Immediate coding sequence

The next steps after this lesson are:

1. Manually verify Auger's coordinate and angle convention.
2. Build a synthetic known-direction shower.
3. Recover it with linear and constrained weighted fits.
4. Implement `src/auger_reco/physics/plane_front.py`.
5. Create `notebooks/02_fit_plane_front.ipynb` for event `81847956000`.
6. Freeze our prediction before revealing Auger's reference direction.
7. Calculate angular separation and inspect every station residual.

## 20. Understanding checks and settled answers

1. If a station is observed $18$ ns later than predicted and $dt=6$ ns, then
   $e=+18$ ns and $q=+3$.
2. With 24 stations and three constrained-fit parameters, the degrees of freedom
   are $24-3=21$.
3. A large reduced chi-square does not uniquely identify a direction error; it can
   also reveal curvature, underestimated `dt`, outliers, correlations, units, or
   optimization problems.
4. A curved or bowl-shaped spatial residual pattern can indicate shower-front
   curvature.
5. Near the zenith, tiny horizontal-component changes can cause large azimuth
   changes while the full 3D direction barely moves, so angular separation is more
   stable.
6. The test set must remain untouched so choices about features, models, and
   thresholds are not adapted to its answers.

## 21. Key takeaways

- A fitted angle is not a scientific result until its residuals and stability have
  been examined.
- Larger `dt` reduces a standardized residual for the same raw timing error.
- Reduced chi-square is a diagnostic of the model-and-uncertainty system, not a
  verdict on direction by itself.
- Synthetic recovery, convention verification, and geometry checks precede real
  interpretation.
- Angular separation is the primary event-level direction error.
- The single JSON event validates the pipeline; a frozen multi-event cohort supports
  research conclusions.
- ML corrects an understood physics baseline and must prove improvement on untouched
  events without leaked inputs.
- Phase 1 ends with reproducible scientific conclusions; deployment belongs to
  Phase 2.

