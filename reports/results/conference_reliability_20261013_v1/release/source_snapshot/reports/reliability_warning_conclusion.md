# Stage B — a local directional-uncertainty warning is not a general safety gate

Completed 2026-10-13 Pacific time (2026-10-14 UTC). This is a separate synthetic
follow-up to the frozen conference study. No original research outputs, measured
events, protected cohorts, fitter source, commits or remote branches were changed.

## Scientific question and decision

**Can the fitted local direction uncertainty identify reconstructions with a
true angular error greater than 1 degree, without knowing the true direction?**

The answer in this deliberately difficult, fixed synthetic benchmark is:
**the diagnostic is informative for some well-specified cases, but the tested
single-threshold warning is not reliable enough for promotion as a safety gate.**
It does not correct any reconstructed direction. Its reduction of error among
retained cases is a selection-conditioned comparison with explicitly measured
retention, not an improvement of the original fitter's accuracy.

None of the nine prespecified candidate thresholds met the development targets
of at least 90% sensitivity and at most 30% false-warning rate. Following the
predeclared fallback, the highest balanced-accuracy candidate—**nominal 95%
ellipse major-axis radius greater than 1 degree**—was frozen and evaluated as
an **exploratory, non-development-viable rule**. No held-out tuning was performed.
Failed fits, unavailable uncertainty calculations, and curvature-boundary fits
also warn. Boundary fits remain included in every performance denominator.

## Experiment

- 36 development settings and 36 independently generated validation settings,
  each with 100 trials: **7,200 attempted fits; 7,200 successful fits**.
- Spread, anchored narrow-ring, and anchor-poor narrow-ring geometries. The ring
  occupies a restricted azimuthal sector with little radial variation; these
  are purpose-built stress layouts, not a sample of the actual detector array.
- Development uses 7/13 stations and directions (25°,35°)/(55°,210°). Validation
  uses 8/14 stations and (35°,100°)/(50°,290°), with an additional 23° layout
  rotation and deterministic 45 m horizontal / 3 m vertical jitter.
- A fixed known synthetic core and quadratic curvature A=200 ns at 1 km are
  supplied/generated. Actual independent Gaussian timing sigma is 12–28 ns.
- Three regimes: correctly specified model/uncertainties; an imposed asymmetric
  mean term with B=80 ns; and a matched mean with reported uncertainties half
  their actual values. The asymmetry amplitude is an intentionally strong toy
  stress, not a measured Auger detector correction.
- The three regimes share noise for each geometry/direction/trial. Thus each
  split has 3,600 fits but 1,200 independent Gaussian-vector draws, evaluated
  under three paired settings. No claim of 3,600 independent regime comparisons.
- Validation changes geometry instances, counts, directions and random streams,
  but uses the same three layout-family definitions and regime families. It is
  **not** an evaluation on wholly unknown geometry or noise families.

The runtime policy sees no truth or reference direction. It uses only the fitted
sky vector and curvature, station coordinates, supplied core and reported timing
uncertainties. Local covariance is computed by the Stage A independent
tangent-plane SVD method, marginalizing fitted time and curvature. There is no
reduced-chi-square rescaling. These are conditional-core local uncertainty
estimates, not total detector uncertainty or proof of frequentist coverage.

## Development-only selection

| Threshold (degrees) | Sensitivity | False-warning rate | Retained fraction | Viable? |
|---:|---:|---:|---:|:---|
| 0.25 | 100.00% | 90.60% | 5.56% | No |
| 0.50 | 87.03% | 76.07% | 19.44% | No |
| 0.75 | 79.43% | 53.36% | 35.97% | No |
| **1.00** | **76.51%** | **45.13%** | **42.03%** | **No; frozen fallback** |
| 1.50 | 51.12% | 21.30% | 66.50% | No |
| 2.00 | 34.83% | 12.41% | 78.42% | No |
| 3.00 | 22.61% | 4.98% | 87.81% | No |
| 5.00 | 10.66% | 4.98% | 92.69% | No |
| 10.00 | 0.81% | 0.14% | 99.58% | No |

The threshold was not revised after seeing validation. The policy itself states
`development_viable: false`; it must not be silently enabled as a production
selection rule or described as a validated detector-quality classifier.

## Independent validation results

There were no fit failures. Every attempted validation event is therefore
included below; all 3,600 fit-only uncertainty calculations were available.
Fifty-nine curvature-boundary fits were explicitly warned rather than discarded.

| Validation regime | Retained / attempted | Detected large errors / all large errors | False warnings / errors ≤1° | Missed large errors / retained |
|:---|---:|---:|---:|---:|
| Matched mean and uncertainties | 400 / 1,200 | 421 / 421 (100.00%) | 379 / 779 (48.65%) | 0 / 400 (0.00%) |
| Asymmetric mean | 400 / 1,200 | 800 / 1,199 (66.72%) | 0 / **1** | 399 / 400 (99.75%) |
| Underreported uncertainties | 500 / 1,200 | 391 / 421 (92.87%) | 309 / 779 (39.67%) | 30 / 500 (6.00%) |
| **Fixed equal-mixture total** | **1,300 / 3,600 (36.11%)** | **1,612 / 2,041 (78.98%)** | **688 / 1,559 (44.13%)** | **429 / 1,300 (33.00%)** |

For comparison, retaining every successful reconstruction gives 2,041/3,600
large errors (56.69%). The warning lowers this selected fraction to 33.00%, but
retains only 36.11% of the results and leaves **429 large errors unflagged**.
That is not an adequate general reliability guarantee.

Approximate 95% Wilson Monte Carlo intervals for the single-regime retained-error
risks are 0–0.951% (matched), 98.598–99.956% (asymmetric), and 4.235–8.436%
(underreported). The matched sample's zero observed misses is not proof that
future misses are impossible. The asymmetric false-warning result 0/1 is
uninformative: its Wilson upper limit is 79.35%, not a precisely measured zero.
Scenario-level intervals are also saved. Overall and layout-pooled intervals are
deliberately omitted because their regime rows share random noise; treating them
as independent binomial observations would overstate precision. All intervals
concern this fixed simulation design, not a detector-event population.

| Regime | All-fit 95th-percentile error | Unflagged 95th-percentile error | Mean nominal reduced chi-square |
|:---|---:|---:|---:|
| Matched | 3.791° | 0.382° | 0.980 |
| Asymmetric mean | 3.700° | 2.005° | 1.371 |
| Underreported uncertainties | 3.791° | 1.063° | 3.919 |

## Interpretation

1. **Local uncertainty can recognize some geometric imprecision, but at a high
   warning cost.** In the matched validation settings, the frozen rule catches
   every observed >1° error, while warning on almost half of the ≤1° results and
   retaining only one third of all reconstructions. This result is conditional
   on this finite, fixed set of geometry instances and the exact supplied core.
2. **Incorrect uncertainties create overconfidence.** The underreported-dt
   regime shares the matched observations and has the same large-error count,
   but narrower nominal local uncertainties allow 30 large errors to pass. A
   nominal confidence radius depends on the validity of the supplied sigma.
3. **A narrow local uncertainty does not detect all systematic bias.** In the
   deliberately asymmetric validation data, 399 of 400 unflagged results still
   exceed 1°. Mean nominal reduced chi-square is only 1.371 over that regime.
   This supports the distinction between local precision, mean-model adequacy,
   and true directional accuracy; none can be substituted for another.
4. **The negative decision is itself the result.** We do not deploy the warning
   as a safety gate, retune its threshold on validation, reject stations, or
   inflate uncertainties merely to obtain satisfactory chi-square. More complex
   warnings or model-discrepancy treatment require a new protocol and fresh
   validation. This study does not prove that every possible warning must fail.

Poster-safe statement:

> A development-locked local-uncertainty warning detected 79% of >1° errors in a
> held-out synthetic stress mixture, but retained only 36% of events and left
> 33% of retained directions above 1°. It was not promoted as a reliability gate;
> systematic timing-model mismatch can remain hidden behind a narrow local
> directional uncertainty.

## Reproducibility and integrity

Canonical artifacts:
`reports/results/conference_reliability_20261013_v1/stage_b/`.

- `locked_policy.json`: SHA256
  `12348c3b22f9c37f6a34a486646eb3e54890066fe925c740963fafb1542161b3`.
- Policy locked at 2026-10-14 02:23:05.482427 UTC; sealed at
  02:23:05.483791 UTC; validation generation began at 02:23:05.483994 UTC.
  Exact bytes were checked before every validation scenario and on completion.
- Development records SHA256
  `3a82381cbf17f8d2beb908c247dedd89464eaba7ee3b7b4dc61cd0cbb345faa0`.
- Archived positions, core, truth, means, actual/reported uncertainties, every
  noise draw and observed time; raw successful/failed outcome schema; fitted
  sky vectors, core times and curvature; all optimizer attempts; source and
  protocol snapshots; selection table; phase timestamps; package versions;
  per-scenario/per-regime/overall metrics and PNG/SVG figure.
- 20,004 development and 19,759 validation internal optimizer starts are
  retained, in addition to 7,200 public fit outcomes. No covariance failures
  occurred; typed failure handling was separately unit-tested.
- Manifest covers 166 archived artifacts. Snapshot/current-source equality
  checks passed at run completion. The Stage A helper version used is SHA256
  `f80aa94d7a928f30fe31d0056284820a91b123f5ad280b46bc0139255ee1bba9`.
- 34 dedicated tests passed with warnings treated as errors; new module and
  tests passed formatting/lint. Tests include fit-only truth exclusion,
  development-only threshold selection, locked-policy tampering detection,
  disjoint split/smoke streams, unchanged paired observations under wrong dt,
  covariance-failure isolation, and explicit failure denominators.
- The separately archived one-trial infrastructure smoke is not counted.
  Production's fresh seed/namespace amendment is documented in the protocol;
  no scientific settings were tuned in response to smoke or Stage A outcomes.

To reproduce, use a **new** output directory. Existing runs are create-only.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m auger_reco.evaluation.reliability_warning \
  --output reports/results/conference_reliability_reproduction/stage_b \
  --trials 100
```

The figure `stage_b/warning_validation.png` (also vector SVG) was visually
checked. Its plotted operating points compare the single frozen rule with a
no-warning baseline; they are not a validation-tuned threshold curve.
