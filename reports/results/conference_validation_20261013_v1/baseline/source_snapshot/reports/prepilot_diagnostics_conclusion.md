# Pre-pilot diagnostics and readiness decision

Authoritative run: [20261010T234353_804166Z](results/prepilot_diagnostics_20261010T234353_804166Z/).
Notebook: [07_pre_pilot_diagnostics.ipynb](../notebooks/07_pre_pilot_diagnostics.ipynb).
Design: [pre-pilot protocol](../docs/prepilot_diagnostics_protocol.md).
All analyses use only the existing focus event and 19 preselected training events.

## What explains the focus-event discrepancy?

At the same published core and with identical station measurements and weights,
the free-direction quadratic fit has chi-square 93.0434 and RMS 96.714 ns.
Fixing the direction to the published SD reference, and refitting time and
curvature, gives chi-square 136.8282 and RMS 116.101 ns. Thus our current
quadratic timing model genuinely prefers a different direction; this is not
merely a degrees-of-freedom or display issue. It does not establish which
direction is closer to physical truth. A delta-chi-square p-value is not claimed.

The focus event's maximum leave-one-station-out direction shift is 0.1478 degrees
(station 822). It is not the most unstable development event. Two previously
identified adverse held-out cases have much larger shifts:

| Event | Full selected stations | Largest direction shift | Omitted station |
|---|---:|---:|---:|
| 130237366100 | 7 | 12.7939 degrees | 833 |
| 112954615400 | 8 | 4.3710 degrees | 763 |

Those stations are influential under the model; this does not establish that
they are faulty or unrelated triggers. They remain included. Their high-gain
saturation flag is 1, which is not the same as both-gain saturation (2).

## Core and signal modelling: implemented, not yet promoted

The new experimental estimator fits horizontal core location and signal
normalization using a softened modified-NKG lateral signal profile. It uses our
plane direction, selected detector signals and their uncertainties, and the
published core altitude. No published x/y core, direction, energy or reconstructed
station distances initialize this estimator. Six fixed beta/gamma combinations
are reported rather than selecting whichever agrees best with Auger.

- All 120 real-event model attempts converged; 114 passed the numerical/domain
  checks. Six solutions for one event reached the search boundary, producing core
  displacements of several kilometres. Convergence is not physical validity.
- Across the six focus-event shapes, reference-direction separation ranges from
  0.2751 to 0.4998 degrees, versus 0.5520 degrees with the published fixed core.
  That apparent improvement alone cannot justify selecting a shape.
- For the fixed central shape beta=-3, gamma=1, every held-out station's time and
  signal were removed before refitting the complete plane→signal-core→quadratic
  chain. All 208 folds converged, but nine carried core-boundary warnings.
- Held-out normalized timing MSE improved in only **6/20 events** compared with
  the published-core-assisted quadratic baseline. For the focus event, held-out
  RMS changed from 114.812 to 115.842 ns: slightly worse, not better.

Accordingly, **the signal estimator remains experimental**. The surrogate
log-signal objective lacks Auger's calibrated shape dependence, full signal
likelihood, operational non-triggered-station information, and saturation-recovery
metadata. It also holds direction and altitude fixed during signal fitting.
No joint timing/signal likelihood or independent-core accuracy is claimed.

## Independent controlled checks

All 2,232 timing fits completed across two geometries, three true directions,
four generators, three fitting methods and 30 paired noise realizations plus
noise-free controls. Matched noise-free recovery passed. The expanding-sphere
generator was checked against an independently expressed distance equation.

The following values summarize six fixed geometry/direction cases; they are not
real-event population performance or confidence intervals:

| Generator; quadratic fit at true core | Median of case-median true angular errors | Median of case-mean nominal reduced chi-square |
|---|---:|---:|
| Quadratic | 0.0939 degrees | 1.0165 |
| Exact expanding sphere | 0.5109 degrees | 2.0350 |
| Quadratic + coherent 100 ns/km timing gradient | 2.1468 degrees | 1.1769 |

This demonstrates model-mismatch and systematic-error sensitivity. In particular,
chi-square near one does not certify correct direction. The injected gradient
is a controlled stress test, not a measured Auger calibration defect. A further
120 paired toy signal/timing chains tested matched and mismatched lateral shapes;
their tables and all outcomes are saved. These are not particle/detector Monte Carlo.

## What is ready for the larger cohort?

The scientifically defensible next batch is a **baseline comparison**, using
the plane and explicitly published-core-assisted quadratic models with timing
and uniform weights. The new signal model is not a default replacement.

- Frozen settings and reporting/failure policy: `pilot_baseline_contract.json`
  in the authoritative run.
- Target-free execution list: `pilot_execution_target_free.csv` in that run.
  It preserves all existing identifiers and splits: 711 train, 145 validation,
  144 test. It contains only ID, split, release and input path.
- No uncertainty inflation, residual clipping, event replacement, or silent
  substitution for failed fits. A >1 degree leave-one-out warning is descriptive,
  not an outcome-selection rule. Six-station events can have a successful full
  quadratic fit but insufficient stations for its held-out fits; report that.
- Implement checkpointed batch execution under this contract next. Develop on
  the training split; keep protected outcomes sealed until the entire relevant
  analysis is frozen. Do not consume the future ML test set for iteration.

The 1,000-event pilot **has not been run**. The project does not yet have an
independent detector-calibrated core/direction estimator or a solved real-event
chi-square discrepancy. Those limitations are now measured and documented.

## Verification and provenance

399 tests passed with warnings treated as errors; source, tests and Notebook 07
passed Ruff. All five notebook code cells executed in a fresh project kernel.
Four saved figures were visually inspected. A separate calculation independently
recomputed all 40 fixed-direction objectives and all 120 signal objectives;
artifact hashes and the target-free manifest were checked. The executed notebook
and an execution receipt are archived. The previous real-event run is unchanged.
No commits were made.

Primary references: [Auger field and reconstruction documentation](https://opendata.auger.org/data.php)
and [surface-detector reconstruction paper, Sections 5.1–5.2](https://arxiv.org/abs/2007.09035).
