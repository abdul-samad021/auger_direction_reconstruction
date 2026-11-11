# Conference controlled stress study: scientific conclusion

Conference release date: 13 October 2026 (America/Vancouver). Authoritative
results: `reports/results/conference_validation_20261013_v1/stress/final/`.
The frozen protocol is `docs/conference_stress_protocol.md`; sources, generated
observations and every fit outcome are preserved with hashes. No real event or
protected validation/test split was read in this experiment.

## Question and experimental scope

Does the improvement from a known-core quadratic timing front persist when
front symmetry or timing-error assumptions are violated, and does uncertainty
weighting retain its advantage?

The predetermined grid uses three deterministic layouts (well-spread,
elongated, one-sided), 7 or 13 stations, two true sky directions, six mean/noise
regimes, and 100 paired trials per scenario. This gives **72 scenarios, 7,200
synthetic datasets and 28,800 fits**. Each dataset is fitted by plane/quadratic
models with timing/uniform weighting. True direction is used only to generate
and evaluate data, never to initialize the fit. The quadratic fitter receives
the **known true core**, so these are core-assisted tests, not an independent
core reconstruction demonstration.

The independent generator uses 80 ns quadratic delay at 1 km. The asymmetric
regime adds a 30 ns azimuthally varying coefficient proportional to squared
transverse radius. Separate regimes introduce nonlinear radius/toy-signal
dependence of actual timing sigma, radius-dependent underreporting of dt,
standardized Student-t(5) noise, or centered exponential noise. The latter two
have population mean zero and variance one. The asymmetric mean is a distinct
deterministic change, not a noise-distribution change. All coefficients are
uncalibrated stress choices, not measurements of Auger shower/detector physics.

## Main results

Every table entry below is a descriptive summary of this fixed grid. Angular
columns are the **median across 12 scenario medians** (each based on 100 trials),
not a pooled-event median or a detector angular resolution. The last column is
the **median across 12 scenario means** of nominal reduced chi-square.

| Synthetic regime | Timing-plane angular error (deg) | Timing-quadratic angular error (deg) | Uniform-quadratic angular error (deg) | Timing-quadratic nominal reduced chi-square |
| --- | ---: | ---: | ---: | ---: |
| Calibrated Gaussian, symmetric mean | 3.516013 | 0.217386 | 0.221935 | 0.994946 |
| Asymmetric mean, Gaussian scatter | 3.174799 | 0.779659 | 0.745208 | 1.722450 |
| Radial sigma, correctly reported | 0.635446 | 0.449949 | 0.746640 | 0.986888 |
| Same radial scatter, underreported dt | 1.824422 | 0.583191 | 0.746640 | 4.600261 |
| Finite-variance heavy-tail t(5) | 3.532859 | 0.184886 | 0.189968 | 0.984347 |
| Centered skew noise | 3.512276 | 0.197118 | 0.219250 | 1.029795 |

1. **Matched curvature continues to help on this grid.** Timing-weighted
   quadratic fitting has positive median paired angular improvement over the
   timing-weighted plane in all 12 scenarios of each symmetric-mean regime.
   This includes nonlinear heteroscedasticity and the non-Gaussian noise cases.
   It does not imply universal superiority under other generators or geometries.

2. **Mean-front asymmetry produces substantial directional bias.** The summary
   angular error increases from 0.217386 to 0.779659 degrees, despite supplying
   the correct core. For the one-sided 13-station, 55-degree-zenith scenario,
   the median true error is 0.850476 degrees while the mean nominal reduced
   chi-square is only 1.197518 (the matched Gaussian case is 0.316709 degrees
   and 1.018415). A relatively reassuring timing diagnostic does not establish
   accurate direction recovery when the mean model is wrong.

3. **Keep the adverse curvature cases.** Under asymmetry, quadratic fitting
   improves median paired true angular error in 10 of 12 scenarios but worsens
   it in both 13-station well-spread cases. With improvement defined as plane
   minus quadratic angular error, these paired medians are:
   - Zenith 25 degrees, azimuth 20 degrees: **-0.356279 degrees**, individual
     95% paired-trial percentile-bootstrap interval **[-0.365331,-0.347469]**.
   - Zenith 55 degrees, azimuth 210 degrees: **-0.055326 degrees**, interval
     **[-0.056750,-0.053494]**.
   Both fit the timing objective successfully; lower objective alone cannot
   order their truth errors. These intervals quantify Monte Carlo variability
   in specified scenarios, are not simultaneous multiplicity-adjusted discovery
   claims, and do not represent uncertainty for a real detector population.

4. **Incorrect dt changes the fit, not just the goodness-of-fit label.** The
   radial calibrated and radial-underreported cases have identical observed
   timings, true directions and actual noise sigma for each paired trial.
   Altering only reported dt changes the timing-weighted angular summary from
   0.449949 to 0.583191 degrees and the nominal chi-square summary from 0.986888
   to 4.600261. Uniform angular results remain identical. Timing weighting
   nevertheless still improves the median paired quadratic angular error over
   uniform weighting in all 12 underreported scenarios: miscalibration is not
   evidence that weights should simply be abandoned.

5. **Weighting is not uniformly beneficial under mean-model mismatch.** In the
   asymmetric regime, timing weighting improves the quadratic median paired
   angular error in 5 scenarios and worsens it in 7. Five individual intervals
   exclude zero in each direction; two remaining negative medians have intervals
   spanning zero. This contrasts with all 12 positive medians under calibrated
   radial uncertainty. A correctly reported random-error scale does not repair
   a systematically incorrect mean front.

6. **Non-Gaussian robustness requires more than a median.** The heavy-tail and
   skew distributions are more concentrated near small errors than Gaussian
   noise in some respects; their smaller angular medians are not a general
   robustness improvement. The medians across scenario p95 angular errors are
   0.573852 degrees (Gaussian), 0.596854 (t5), and 0.622425 (centered skew).
   Scenario-level p68/p95 values and paired intervals are retained in the tables.

## Validation and failure accounting

- **28,800/28,800** requested noisy fits returned numerical successes; no failed
  trial was discarded. The runner and regression tests retain failure category,
  message and available optimizer attempts, including an all-failed scenario.
- **96 noiseless controls** were run: 72 matching-model recovery controls passed
  direction/timing tolerances, and 24 plane-on-curved controls intentionally
  represent mismatch rather than requiring exact direction recovery.
- **14,400** matched-weight plane/quadratic objective nesting checks passed;
  there were zero violations.
- **48 of 14,400 quadratic fits** reached the curvature lower-bound diagnostic.
  These are retained, not silently treated as ordinary interior chi-square fits.
- All 30 experiment-specific tests pass with warnings treated as errors; source
  and test formatting/lint checks pass.
- An independent audit imports neither production predictor nor fitter. It
  recomputes predictions from saved parameters, angular errors via a separate
  half-angle formula, objectives/RMS/nominal chi-square, generated mean fronts
  via cross-product radii, observation pairing, and all artifact/source hashes.
  Across all 28,800 fits the maximum relative objective difference is
  **1.01e-11**, maximum RMS difference **2.71e-11 ns**, and maximum angular
  difference **8.89e-15 degrees**. All 157 archived artifacts pass their hashes.
- A reporting-only correction clarified the improvement-tolerance column and
  hardened all-failed-scenario output. The final run reproduces all **28,800 fit
  records exactly** from the initial full execution. The smoke run and first
  full run are preserved for provenance, not counted as independent evidence.

## Interpretation and conference claim

> In a prespecified controlled timing study, a known-core quadratic front
> substantially improved direction recovery for symmetric curved fronts across
> Gaussian, heteroscedastic and non-Gaussian noise. An asymmetric mean front
> produced persistent directional errors and two adverse curvature cases, while
> misreported uncertainties altered both direction estimates and nominal fit
> diagnostics. These results motivate model-mismatch and stability checks in
> addition to residual goodness-of-fit.

This study does not calibrate real-event angular uncertainties, identify the
actual cause of any particular real-event residual, estimate the core, or claim
superiority to Auger's reconstruction. Three fixed layouts and two directions
are a bounded mechanism test, not a representative shower population. The
nonnegative curvature boundary, model nonlinearity and non-Gaussian regimes
preclude interpreting nominal chi-square as a universal calibrated significance.
No robust-loss or new asymmetry fitter is promoted based on this experiment;
such a method requires its own predeclared validation rather than tuning these
generators until the desired result appears.

## Reproduction and artifacts

From the project root with its environment active:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m auger_reco.evaluation.conference_stress \
  --output reports/results/conference_validation_20261013_v1/stress/final --trials 100
python reports/results/conference_validation_20261013_v1/stress/audit_stress_results.py
pytest tests/test_conference_stress.py -W error
```

Existing completed scenarios resume only under the identical source/configuration
fingerprint. A changed study requires a new output directory. The final run's
`scenario_summary.csv`, `paired_contrasts.csv`, `summary.json`, and
`stress_comparison.png`/`.svg` are the presentation inputs. Full per-seed solver
diagnostics and all generated arrays remain in per-scenario JSON/NPZ files.
`stress/independent_audit.json` records the independent audit result.
