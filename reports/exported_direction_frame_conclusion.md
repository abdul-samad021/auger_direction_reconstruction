# Exported direction-frame audit and correction - 14 October 2026

## Scientific decision

The released station/core `x,y,z` are consistent with a central-site ENU
Cartesian frame. The released `sdrec.theta/phi` are consistent with the local
east-north-up frame at each event's core. The historical comparison treated
their components as if they shared a frame. **Correct that comparison, not the
timing model or the station coordinates.**

This decision follows Auger correspondence, its public WGS84 geometry
description, and numerical consistency checks using redundant released fields.
It is empirical export verification, not inspection of unavailable exporter
source, independent survey validation, or absolute-pointing calibration.

## Scope, independence and evidence

Only the 711 previously studied training events and the old focus event
081847956000 were opened. The 145 validation and 144 test events remain unopened.
No fit was rerun, no station was rejected, no uncertainty was rescaled, and no
historical result was overwritten. The corrected table has 2,848 rows: four
saved full-event fits (two models and two weightings) for each of 712 events.

The transformation was tested against `spDistance`, core coordinates, and
declination rather than chosen to optimize agreement with our fitted directions.
These are redundant Auger outputs, not independent true directions.

| Check | Direct central-site interpretation | Core-local interpretation |
|---|---:|---:|
| Median of per-event median absolute axis-distance discrepancies | 0.805565 m | 0.016904 m |
| Selected stations within conservative rounding envelope | 1,217/5,661 | 5,661/5,661 |
| Median absolute declination discrepancy | 0.088469 deg | 0.002798 deg |
| Declinations within conservative rounding envelope | 59/712 | 712/712 |

All 712 events have smaller axis-distance discrepancies under the core-local
interpretation. WGS84 UTM/ECEF conversion reproduces every published core
position within 0.010 m in each component. The supplied UTM origin confirms
35.25 S, resolving the tutorial's inconsistent 35.35 S comment.

The rounding envelope assumes angles exported to 0.01 degrees and positions/
distances to 0.01 metres. It is a conservative numerical consistency check,
not a measured detector uncertainty or a statistical confidence interval.

## Corrected comparisons

All numbers below are angular separation **from Auger's reconstructed reference**.
They must not be labelled real-event true error or superiority to Auger.

| Population / method | Historical mixed-frame separation | Corrected common-frame separation |
|---|---:|---:|
| Focus event, timing-weighted plane | 0.263897 deg | 0.310355 deg |
| Focus event, timing-weighted quadratic | 0.551962 deg | 0.522484 deg |
| 711 training events, timing-weighted plane median | 1.106043 deg | 1.077334 deg |
| 711 training events, timing-weighted quadratic median | 0.306573 deg | 0.255079 deg |
| 711 training events, uniform plane median | 1.593517 deg | 1.575799 deg |
| 711 training events, uniform quadratic median | 0.719531 deg | 0.662888 deg |

The timing-weighted quadratic model is farther from the reference than the
plane model for **43/711** events (historical count 61/711). For uniform weighting,
the corrected count is **103/711** (historical 101/711). Both favourable and
unfavourable results are retained.

Timing-weighted 95th-percentile reference separations change from
4.278691 to **4.181923 degrees** for plane and from 0.683756 to
**0.589591 degrees** for quadratic. These are distribution quantiles, not
confidence limits. Historical bootstrap intervals for reference contrasts are
not reused after the correction.

The focus event's central story survives: curvature improves timing, but its
reference separation still increases, now **0.31 to 0.52 degrees**. The overall
training reference agreement is modestly better after the frame correction.
This is a reporting/evaluation correction, not an improved reconstruction model.

## What did not change

- Predicted station times, residuals, RMS values and nominal chi-square.
- Conditional held-out timing performance.
- Within-event angular shifts between full and station-omission fits.
- Curvature parameters and core-dependence experiments.
- Known-truth synthetic errors and uncertainty-coverage results.
- The frozen data split, historical input files, or fit parameter vectors.

The corresponding plane/quadratic dot products and perpendicular-axis distances
are invariant under a consistent rigid frame rotation. Forward checks differed
by only 4.55e-12 ns, a floating-point result, not a detector-precision claim.

## Reproducibility and poster action

Final results are in `reports/results/exported_direction_frame_20261014_v2/`:

- `corrected_reference_comparisons.csv`: current common-frame values and angles.
- `saved_fit_reference_comparisons.csv`: both interpretations and transformed
  fitted vectors; original saved vectors are retained.
- `event_redundancy_checks.csv` and `selected_station_redundancy_checks.csv`.
- `summary.json`, input/artifact hashes, protocol, versions and exact audit source.

The original `scripts/audit_exported_direction_frame.py` execution used pyproj
3.7.2 installed outside the production environment. The later integration added
the same version to the locked project dependencies. At the original audit,
both old and new coordinate tests passed:
**39 tests**, including 23 new tests. See the reproduction commands and formulas
in `docs/conference_coordinate_audit.md`.

An independent read-only verification checked all eight artifact hashes and
1,427 input hashes, verified every training checkpoint, and reproduced all 2,848
separations in ECEF using a separately constructed ENU basis. The maximum
difference was 1.56e-14 degrees. Every saved site-frame fitted vector matched
its original prediction exactly.

The current poster needs three numerical changes: focus reference separation
**0.26 -> 0.55** becomes **0.31 -> 0.52 degrees**; training medians
**1.11 -> 0.31** become **1.08 -> 0.26 degrees**; **61/711** farther becomes
**43/711**. State that reference directions are compared in a common frame.
The main timing, instability and synthetic figures do not need to change.

The original audit was a bounded postprocessing correction. The subsequent
production integration now uses `data/direction_reference.py` automatically in
real-event notebooks, batch comparisons, and the pre-pilot reference-assisted
diagnostics. See `docs/direction_frame_integration.md`. Historical saved runs
remain legacy; their numerical evidence is not overwritten or relabeled. The
correction is not a reason to refit the frozen conference research package.
