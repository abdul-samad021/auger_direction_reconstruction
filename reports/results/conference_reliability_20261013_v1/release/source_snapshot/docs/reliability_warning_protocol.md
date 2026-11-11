# Stage B: independently evaluated directional-reliability warning

Protocol recorded before production simulation, 2026-10-13. This follow-up does
not modify the frozen conference baseline or inspect any measured event.

Infrastructure-only amendment before production: the initial one-trial smoke
used master seed 2026101327. Production uses fresh master seed **202610132701**
with an additional namespace component, and any non-100-trial smoke uses a
separate namespace. This prevents inspected smoke observations appearing in
production validation. No geometry, noise regime, threshold candidate, target
or selection criterion was changed in response to smoke results. The smoke is
archived separately and contributes no production counts.

## Question and scope

Can one fit-only local uncertainty diagnostic warn about a reconstructed
direction whose known synthetic error exceeds **1 degree**, including when the
mean timing model or supplied uncertainties are wrong? This is a diagnostic
study, not a new fitter, station rejection procedure, or detector calibration.
The exact generated core is supplied to every quadratic fit. The warning is
therefore conditional on that assumed core and the nominal timing uncertainties.

## Locked design

- Development and validation each contain 36 equally represented scenarios:
  spread, anchored near-ring, and anchor-poor near-ring layouts; two counts; two
  directions; three regimes. Each scenario has 100 noise trials.
- Development counts are 7 and 13; directions are (zenith, azimuth) = (25,35)
  and (55,210) degrees. Validation counts are 8 and 14; directions are (35,100)
  and (50,290) degrees. Validation layouts are independently rotated by 23
  degrees and perturbed with deterministic 45 m horizontal / 3 m vertical jitter.
  All noise streams are keyed by split, geometry, direction and trial. No
  validation observations are generated before the rule is frozen.
- The layouts are deliberately designed toy geometries, not sampled detector
  events. A ring here covers a restricted azimuthal sector; its radial spread
  is deliberately small. The anchored version replaces one station by a
  near-core point. This is an identifiability stress test, not a population
  prevalence estimate or a formal held-out geometry-family generalization.
- The mean is an independently implemented plane plus quadratic delay with
  A=200 ns at 1 km and origin time 100000 ns. Actual Gaussian sigma is
  12+4*(station index modulo 5) ns.
- Regimes are (1) matched mean and reported sigma; (2) an additional asymmetric
  mean B*rho*(d dot e_theta)/1e6 with B=80 ns; (3) matched mean but reported sigma
  half its actual value. Paired noise is shared across the three regimes for a
  given geometry/direction/trial. No correlations or detector response simulated.

## Runtime diagnostic and development-only selection

Use the Stage A tangent-plane, nuisance-marginalized SVD covariance to calculate
the nominal 95% ellipse major-axis angular radius. The helper uses measured
station coordinates, reported uncertainties, assumed core and fitted parameters
only, never true directions or true errors. Do not multiply covariance by fitted
reduced chi-square. Fit failure, unavailable/nonfinite uncertainty, or fitted
curvature on its nonnegative boundary always produces a warning.

For otherwise eligible fits, warn if that radius is greater than a selected
threshold. The only candidates, in degrees, are
**0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10**.

Development selection uses all successful fits in the prespecified equal
scenario mixture. Large error is strictly greater than 1 degree. A candidate is
development-viable if empirical sensitivity is at least 90% and false-warning
rate at most 30%, with both positive and negative examples present. Among
viable candidates, maximize retained fraction; ties choose the larger threshold.
If none qualifies, select highest balanced accuracy (mean sensitivity and
specificity), ties choose the larger threshold, and mark the policy
**not development-viable**. This fallback is evaluated as a negative/exploratory
diagnostic, never rebranded as a validated safety gate. No validation tuning.

Write immutable `locked_policy.json` and its SHA256 receipt before generating
validation observations. Archive the development candidate table, data,
protocol, implementation, covariance helper and fitter sources. Verify the
policy hash before each validation scenario and on completion. A new run must
use a new output directory; existing artifacts are never overwritten.

## Reporting and stopping

Record every requested fit, including typed failures and all optimizer attempts.
Save positions, reported/actual uncertainties, truth, means, random noise,
observations, fitted sky vectors and curvature. Report per scenario, regime and
overall: successful and failed counts, unconditional warning/retention fractions,
successful-fit sensitivity, false-warning rate, missed-large-error count,
precision, and large-error risk among unflagged successful fits, with approximate
Wilson 95% Monte Carlo intervals for scenario and single-regime groups where
defined. **Omit intervals for overall/layout mixtures pooling paired regimes**;
their correlated rows must not be counted as independent Bernoulli draws. Fit
failures always warn but are not assigned a
fabricated directional error or counted as correctly detected angular errors.
Report a no-warning baseline retaining all successful fits (failures still
unavailable), raw and retained angular-error quantiles, and the actual frozen
policy operating point. Candidate operating-point tables are development-only.

The scenario Wilson intervals describe repeated independent Monte Carlo draws
at a fixed setting. Single-regime pooled intervals are approximate descriptive
Monte Carlo intervals over a fixed, equally sampled mixture of settings, not
uncertainty about a detector-event population. Regimes have paired noise and
must not be treated as independent comparisons.
The scope stops after independent validation and its scientific assessment,
whether useful or not. No ML, new core fitting, post hoc threshold search, real
event selection, protected-cohort evaluation, or forced chi-square reduction.
