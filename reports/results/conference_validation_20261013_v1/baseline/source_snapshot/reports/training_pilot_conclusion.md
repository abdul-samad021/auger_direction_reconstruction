# Training-pilot result: curvature helps substantially, but does not resolve every event

Authoritative run: [`training_pilot_20261011_v1`](results/training_pilot_20261011_v1/report/scientific_report.md).
Executed 11 October 2026 UTC (10 October in Vancouver). This is a completed
**training-stage baseline comparison**, not completion of the full research plan
or a final evaluation of the protected population.

## Design and accounting

The frozen 1,000-event pilot contains 711 training, 145 validation, and 144 test
events. All **711 training events** completed; **the 289 protected events were
not downloaded, fitted, or unblinded**. Nineteen training events had previously
been examined during development; separate summaries identify them. The old
24-station focus event is outside this pilot and was not appended.

For every event, we compared plane and fixed-published-core quadratic timing
models, each with timing-uncertainty and uniform weighting. Official station
selection and released coordinates were retained. No uncertainty rescaling,
residual-based station removal, additional Earth-curvature correction, or
signal-model substitution was introduced. Predictions were saved and hashed
before the published direction was accessed for comparison.

All **2,844 full-event fits** converged. Across full fits and every planned
leave-one-station-out (LOO) attempt, there were **25,392 records**: 22,452
successful fits and 2,940 explicit `InsufficientStations` outcomes. These arise
from 245 six-station events: holding one station out leaves five, below the
frozen quadratic minimum of six. There were no download, input, reference-load,
or other fit-failure categories. No failures or replacement events were hidden.

## Primary timing-weighted observations

Values are medians of per-event metrics, with equal event weight.

| Metric | Plane | Core-assisted quadratic | Common event count |
|---|---:|---:|---:|
| Nominal reduced chi-square | 26.9693 | 1.5256 | 711 |
| In-sample timing RMS, ns | 308.985 | 71.879 | 711 |
| Separation from Auger reference, degrees | 1.10604 | 0.30657 | 711 |
| Conditional held-out timing RMS, ns | 366.335 | 123.981 | 466 |
| Conditional held-out normalized MSE | 55.7004 | 5.9953 | 466 |
| Maximum LOO direction change, degrees | 1.82232 | 0.54877 | 466 |

The last three rows use the **same 466 events for both models**. They must not
be compared against the plane-only summaries over all 711 events.

The quadratic timing-weighted fit had lower nominal reduced chi-square in
710/711 events and smaller reference separation in **650/711**. It had lower
held-out RMS in **452/466** complete pairs and lower held-out normalized MSE in
439/466. The remaining 245 events remain in the accounting, but cannot support
a complete paired quadratic LOO comparison under the frozen station minimum.

These findings support the interpretation that a quadratic curvature term
captures substantial timing structure missed by the plane approximation. The
held-out comparison offers evidence beyond merely reducing an in-sample fitting
objective. However, it remains conditional on a published core and station
selection derived from the full official event reconstruction.

![Paired timing-weighted results](results/training_pilot_20261011_v1/report/training_pairs_timing_log_v2.png)

## What remains unresolved

- The timing-weighted quadratic reduced chi-square has a 95th percentile of
  **12.6846**, and 114/711 events exceed five. A median near one does not establish
  calibrated uncertainties or an adequate model for every event.
- Reference agreement worsened in **61/711 events**. Auger's direction is a
  reconstructed reference, not known physical truth; agreement cannot establish
  true-direction accuracy or superiority to Auger's reconstruction.
- Among the 466 complete quadratic LOO cases, **131** show a direction change
  above one degree. The maximum is **18.5778 degrees** for seven-station event
  `081881294400`, despite a full-fit reference separation of only 0.2379 degrees.
  This illustrates why close reference agreement can coexist with instability.
- All events carry informational geometry/model flags. “Any quality flag” does
  not mean every fit is invalid: `surface_like_geometry`, `known_core_assisted`,
  and `nominal_degrees_of_freedom` are explicit context flags. Curvature-boundary
  flags occur in 23 successful full/LOO fits across both weightings and are
  retained separately. No nested-objective violation was found.

Uniform-weighted results are also saved. For the quadratic model, their median
reference separation is 0.7195 degrees, versus 0.3066 degrees with timing weights;
timing weighting is closer to the reference in 602/711 paired events. Uniform
fits nevertheless have a smaller median in-sample raw timing RMS (53.13 ns versus
71.88 ns), consistent with optimizing a different loss. A lower raw RMS must not
be confused with a better uncertainty-weighted objective or direction estimate.

## Reproducibility and claim limits

The run preserves each event's input checksum, full/LOO records, station residuals,
optimizer attempts, reference comparison, source snapshots, and configuration.
All **438 automated tests** pass with warnings treated as errors; lint and
format checks pass. Re-running the completed batch scheduled **zero** new fits
or downloads.

The [independent audit](results/training_pilot_20261011_v1/independent_audit.json)
verified every raw/source/checkpoint hash, every expected fit record, all 22,452
successful fits' numerical metrics, and 2,844 reference separations using
separate vector formulas. Maximum prediction disagreement was
`2.3842e-7 ns`; maximum relative objective discrepancy was `1.3798e-8`.
These checks establish internal consistency, not physical truth validation.

The nominal chi-square degrees of freedom do not incorporate all shared-core,
selection, curvature-boundary, or model uncertainties. Held-out normalized MSE
uses only detector timing uncertainties; it is not reduced chi-square or a
calibrated predictive pull. The frozen, selected training sample is not an
unbiased population measurement, and descriptive win counts are not significance
tests. The experimental signal/core model remains a research branch, not a
promoted improvement. No ML model or independent station-selection claim is made.

## Next scientific gate

Investigate the unstable seven-station and high-residual training cases, using
the preserved station influence, timing uncertainty, signal/saturation and geometry
information. Test proposed changes with controlled synthetic truth and a new
documented training experiment; do not remove difficult events or alter sigmas
solely to lower chi-square. Keep the protected splits sealed until model choices,
quality rules, uncertainty treatment and evaluation procedure are frozen.

Artifacts: [event metrics](results/training_pilot_20261011_v1/report/training_event_metrics.csv),
[method and multiplicity summaries](results/training_pilot_20261011_v1/report/training_method_summary.csv),
[paired comparisons](results/training_pilot_20261011_v1/report/training_paired_summary.csv),
[execution protocol](../docs/training_pilot_execution.md).
