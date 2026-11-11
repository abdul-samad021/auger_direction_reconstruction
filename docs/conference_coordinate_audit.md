# Conference coordinate audit

## Current status - 14 October 2026 follow-up

**The released station/core positions behave as central-site Cartesian ENU,
whereas `sdrec.theta/phi` behave as core-local ENU angles. Reference comparisons
must put the two directions in a common frame.** This operational convention is
now established by redundant-field checks on 711 already-observed training
events plus the old focus event, following the Auger team's clarification.

Use `reports/results/exported_direction_frame_20261014_v2/` for the new checks
and corrected reference comparisons, and
`reports/exported_direction_frame_conclusion.md` for interpretation. Historical
results below describe the original 13 October audit; their unresolved-angle
statements and mixed-frame reference comparisons are superseded by this update.
No timing fit, station coordinate, historical result, or protected event changed.

### Evidence and frame transformation

- Auger correspondence confirms the WGS84 ellipsoid, reconstruction angles in
  the tangent plane at the core, and use of actual 3D station geometry.
- The [Offline framework paper, section 6.2](https://arxiv.org/pdf/0707.1652)
  independently documents WGS84/UTM and Cartesian coordinate transformations.
  Neither that paper nor the public field table exposes the exact JSON exporter;
  the following verification is empirical, not a claim to have inspected it.
- WGS84 UTM zone 19 south converts the supplied origin (E477256.66,
  N6099203.68 m) to longitude -69.250000049, latitude -35.249999966 degrees.
  This resolves the tutorial's 35.35-degree comment in favour of **35.25 S**.
- UTM -> geodetic -> ECEF -> central ENU reconstructs all 712 published core
  positions to less than **0.010 m per component**, consistent with export
  rounding. Using the supplied altitude numerically as WGS84 height establishes
  exporter consistency; it does not independently certify a vertical survey datum.
- Using core-local angles reduces the per-event median absolute `spDistance`
  mismatch in **712/712 events**. The median of that event statistic falls from
  **0.805565 to 0.016904 m**. All **5,661/5,661** selected station distances pass
  the conservative rounding envelope, compared with **1,217/5,661** when the
  angles are incorrectly interpreted directly in the central-site frame.
- The independent declination redundancy check also supports core-local angles:
  median absolute discrepancy falls from **0.088469 to 0.002798 degrees**, with
  **712/712** within the conditional angle-rounding envelope (formerly 59/712).
  This check uses no RA/time transformation or our fitted direction.

Let B0 and Bc contain the east, north, up unit vectors as columns in ECEF at the
site origin and the event core. Construct the usual upward sky vector from the
published angles in the core frame. Then

$$s_{\rm reference,site}=B_0^{\mathsf T}B_c\,s_{\rm reference,core},$$

or, equivalently, transform the saved fitted vector:

$$s_{\rm fit,core}=B_c^{\mathsf T}B_0\,s_{\rm fit,site}.$$

Both give the same angular separation. The saved audit checks this equivalence,
orthonormality, handedness, round trips, and full 3D plane/quadratic timing
invariance. No constant azimuth or zenith offset is applied.

The correspondence's approximate 0.25-degree scale is **not a universal bound
or a Gaussian uncertainty**. In these 712 events, the actual reference-vector
rotation has median 0.168234 degrees and maximum 0.383087 degrees. The separate
local-vertical tilt has median 0.190167 and maximum 0.341685 degrees. Full basis
rotation and vertical tilt are not interchangeable. These observed frame
differences are removed geometrically, not added as noise or clipped to 0.25.

### Updated reference results (timing weighted)

| Quantity | Historical mixed-frame value | Common-frame value |
|---|---:|---:|
| Focus event plane separation | 0.263897 deg | 0.310355 deg |
| Focus event quadratic separation | 0.551962 deg | 0.522484 deg |
| 711-event plane median separation | 1.106043 deg | 1.077334 deg |
| 711-event quadratic median separation | 0.306573 deg | 0.255079 deg |
| Events where quadratic is farther from Auger | 61/711 | 43/711 |

The distinction is **agreement with Auger's reference**, not accuracy against
truth. The frame decision was supported by released geometric/declination fields,
not selected to improve these comparisons. The focus event still moves farther
from Auger's direction with curvature despite its improved timing prediction.

### Reproduction and historical boundary

The original `scripts/audit_exported_direction_frame.py` execution used
`pyproj==3.7.2` (PROJ 9.5.1) from a separate temporary audit directory. At that
stage the production environment was not modified. These commands reproduce
that original isolated setup; the current project now includes pyproj directly:

```bash
uv pip install --python .venv/bin/python --target /tmp/auger-frame-audit-deps pyproj==3.7.2
PYTHONPATH=/tmp/auger-frame-audit-deps .venv/bin/python scripts/audit_exported_direction_frame.py \
  --root . --output reports/results/exported_direction_frame_reproduction_v1
PYTHONPATH=/tmp/auger-frame-audit-deps .venv/bin/python -m pytest \
  tests/test_exported_direction_frame.py tests/test_conference_coordinates.py -W error
```

The script refuses an existing output directory and records all input hashes,
versions, the audit source, both interpretation scenarios, and common-frame
directions/angles. **39 coordinate tests pass (23 new, 16 existing)**. Timing
forward-invariance discrepancy is below 5e-11 ns; this is a numerical test
tolerance, not detector precision. The new tests skip explicitly when the
optional geodetic dependency is absent.

The subsequent production integration is complete in the current notebook and
evaluation entry points: `data/direction_reference.py` supplies the common-frame
reference automatically, with a versioned provenance record. `pyproj==3.7.2` is
now a locked project dependency; the isolated commands above document the
original audit environment. See `docs/direction_frame_integration.md` for current
commands and legacy-output guards. The timing fitters did not change. Historical
saved results and the immutable 13 October package are not relabeled as though
they already contained the correction.

## Prespecified audit protocol (2026-10-13, before numerical execution)

This is a coordinate-consistency and counterfactual-sensitivity audit, not a new
coordinate calibration. No production fitter, historical input or result is
modified. The population is the 711 training IDs recorded by the completed
`training_pilot_20261011_v1/configuration.json`, plus the previously inspected
focus event `081847956000`. Protected validation/test event files are not opened.

1. Read, do not execute, the official `plot_json.ipynb` in the notebook archive
   linked by the Auger analysis page; preserve its hash and relevant source cells.
2. Independently implement its approximate site-to-UTM/altitude transformation
   and inverse. Compare transformed *published core* coordinates with the
   corresponding published easting, northing and altitude in the same already
   observed event. Also compare the station IDs occurring in these observed
   events with the existing public auxiliary `sdMap.csv`. These redundant fields
   are a consistency test, not independent survey truth; do not infer the exact
   exporter or survey uncertainty from them.
3. Check cardinal sky directions, the propagation sign, origin-time translation,
   rigid rotations about site z, and both forward timing models. Check recovered
   directions for deterministic exact synthetic data under translations and
   rotations. Rotation of all positions, core and direction together must
   preserve geometry; the nonlinear UTM/altitude map is not such a rotation.
4. Quantify the precisely defined *counterfactual* of adding the tutorial's
   altitude term `(x*x+y*y)/(2R)` to site z, using existing timing-weighted plane
   directions. Measure station-dependent timing shifts after removing the fitted
   common time offset. This is not an advocated correction or a bound on an
   unknown real systematic. Refit this counterfactual only for the focus event
   and the preidentified extreme-instability training event `081881294400`.
5. Save source/input hashes, all denominators, deterministic check results,
   conversion residuals and counterfactual results in a new output directory.
   Refuse to overwrite any existing output. Do not use published directions to
   choose a transform or to tune the fitting model.

### Interpretation rules

- Exact mathematical invariances are tested numerically at stated tolerances.
- The tutorial explicitly uses an approximate conversion; finite discrepancies
  against redundant exported fields are reported, not optimized away.
- The geodetic datum, precise exporter and higher-order transformation accuracy
  remain unresolved unless the source establishes them directly.
- Numerical agreement does not independently validate absolute pointing or
  Earth's treatment in the full reconstruction software.

## Primary-source locators

- [Auger analysis page](https://opendata.auger.org/analysis.php), "Reading JSON
  files", download link to the 2024 release archive.
- [2024 notebook archive](https://zenodo.org/records/10488964/files/notebook.zip?download=1),
  `plot_json.ipynb`, coordinate-conversion cell located by the constants `alpha`,
  `beta`, and Earth radius (exact cell index recorded in the output receipt).
- [Auger field documentation](https://opendata.auger.org/data.php), JSON semantics:
  `sdrec.x/y/z` in the site system versus `easting/northing/altitude` in UTM;
  `stations.x/y/z` in site metres and `t/dt` in nanoseconds.
- User-supplied correspondence from Viviana for the Data Release Task confirms
  origin E=477256.66 m, N=6099203.68 m, altitude 1400 m, UTM zone 19H, and azimuth
  0 east, 90 north, 180 west, 270 south. The email does not give the exact exporter
  implementation or geodetic datum and is not reproduced as a public email here.

## Results (completed 2026-10-13)

Saved results: `reports/results/conference_validation_20261013_v1/coordinates/audit_v1/`.
This directory contains the pre-execution protocol, exact notebook archive and
coordinate-cell receipt, input/source hashes, all comparison rows, numerical
invariance checks and counterfactual-only refits. Existing production measurements,
fits and training results were not modified. No protected event files were opened.

### Confirmed conventions and mathematical implementation

The original archive matches SHA-256
`3568191c87dacd42ce26b747c2f1ad31a084cd1d87d3f7f7e841dbcf4e6e6138`.
Cell **32, zero-based**, of `notebook/plot_json.ipynb` contains exactly

$$
E=477256.66+(1-0.000603)x-0.00252y,
$$

$$
N=6099203.68+(1-0.000603)y+0.00252x,
$$

$$
A=1400+z+\frac{x^2+y^2}{2(6368000)}.
$$

The horizontal map is mathematically a rotation of **0.144472 degrees** and
scale **0.9994001771**. Thus site x/y are approximately east/north, not identical
to unrotated UTM easting/northing. The direction fitter correctly continues to use
site coordinates. A coordinate rotation must rotate the reference direction too;
adding 0.144472 degrees to only one direction would create a spurious discrepancy.

The altitude formula is quadratic and the horizontal map is linear, not a full
geodetic transformation. The tutorial does not claim its mathematical truncation
is the exact production exporter. Its previous markdown cell merely asks readers
to convert and compare event coordinates with the detector map.

The code uses an upward sky vector, its negative for downward propagation, and
`t=t_ref+(r-r_ref).u/c`. Positive propagation x gives a later arrival at larger x
when the other coordinates are fixed. Moving the reference origin changes
`t_ref` but does not change the physical vector. **32 deterministic actual fits**
(plane and quadratic, four cardinal azimuths, base/translation/z-rotation/both)
pass direction recovery, timing and curvature checks. Positions, core and vector
are transformed together. Test thresholds are 1e-5 degrees direction, 1e-4 ns
fit residual and 1e-7 ns forward-invariance difference; these are numerical
verification tolerances, not detector precision claims. Sixteen audit unit tests
pass with warnings treated as errors.

### Redundant exported coordinate comparisons

The population is **711 training events plus one previously inspected focus
event**, yielding 712 SD-core comparisons and 1533 unique `(station ID,x,y,z)`
records against the public map. A repeated station-coordinate record is counted
once, so station statistics are not event-frequency weighted. All 1533 records
have a matching map ID; the 1689 map IDs are unique.

Absolute transformed-minus-published residuals, in metres:

| Population | Component | Median | 95th percentile | Maximum |
|---|---|---:|---:|---:|
| 712 SD cores | Easting | 0.1429 | 0.6361 | 0.9324 |
| 712 SD cores | Northing | 0.1390 | 0.4403 | 0.7445 |
| 712 SD cores | Altitude | 0.0416 | 0.1854 | 0.2612 |
| 1533 station-position records | Easting | 0.1388 | 0.6801 | 2.9084 |
| 1533 station-position records | Northing | 0.1327 | 0.4757 | 4.8221 |
| 1533 station-position records | Altitude | 0.0445 | 0.1875 | 13.9375 |

The altitude term itself is substantial: median **39.41 m** across unique station
records, versus median altitude mismatch **0.0445 m** after applying the tutorial
formula. This strongly supports that released site z is **not simply altitude
minus 1400 m**. It does not independently establish the survey datum or exporter.

The station-map outliers must not be hidden. Largest altitude residuals include
station 1850 (13.94 m), 1849 (13.34 m), 1824 (11.70 m), 1778 (10.76 m), and 1799
(9.87 m). The public map is not an event-specific independent survey record; no
cause (survey revision, temporal mapping, approximation or data error) has been
established here, and the station JSON coordinates have not been overwritten.

A **post-hoc descriptive check**, using >1 m in any component to locate obvious
outliers, finds 11 station-position records/IDs. Across the audited events these
IDs occur 12 times selected and five times unselected; 11 events contain at least
one selected occurrence. Neither the focus event nor extreme-instability event
contains one of these IDs. The 1 m threshold is not a predefined quality cut or
validated rejection rule; this observation does not prove their fitted positions
are wrong. Its receipt is `coordinates/station_map_outlier_followup.json`.

### Counterfactual sensitivity, NOT a proposed correction

We deliberately tested `z_new=z+(x*x+y*y)/(2R)` with the x/y coordinates unchanged.
This mixes an altitude-style z with the original site x/y; it is **not a valid
rigid frame change** and not an alternative geodetic solution. Its role is to show
why casually adding the altitude term would change the scientific answer.

For the 712 existing timing-weighted plane directions, the station-dependent
change in predicted timing has median peak-to-peak **28.52 ns** (maximum **83.58
ns**). After removing its inverse-variance-weighted mean, the weighted RMS has
median **6.01 ns**, p95 **10.67 ns**, maximum **15.42 ns**. Removing the common
offset matters because the fitted reference time absorbs a uniform delay.

Refits alter **both station and core z** for the quadratic case:

| Event | Model | Direction shift | Baseline nominal reduced chi-square | Counterfactual |
|---|---|---:|---:|---:|
| Focus 081847956000 | Plane | 0.03464 deg | 72.9305 | 73.3890 |
| Focus 081847956000 | Quadratic | 0.03009 deg | 4.6522 | 4.6618 |
| Instability 081881294400 | Plane | 0.22890 deg | 36.6094 | 36.7094 |
| Instability 081881294400 | Quadratic | 0.22872 deg | 2.6676 | 2.6684 |

These are scenario sensitivities, **not systematic error bars**. They show that
an unsupported coordinate change can tilt direction while barely changing fit
quality. They neither justify that change nor diagnose the extreme leave-one-out
instability (the latter involves the unchanged full-event geometry).

### What is and is not resolved

- **Established:** units, site-coordinate inputs, timing sign, sky/propagation
  distinction, source-backed map constants, numerical translation/rotation
  covariance and broad agreement with redundant projected coordinates.
- **Supported interpretation:** site z and altitude are distinct; the tutorial
  includes an Earth-curvature-related altitude term. An extra blanket correction
  in the fitter is not justified by the evidence.
- **Still unresolved:** exact survey datum, full exporter/higher-order
  transformation and the origin of a small set of station/map discrepancies.
- **Source inconsistency:** the tutorial comments latitude **35.35 S**, while
  Auger's correspondence says **35.25 S**. Our fitter uses neither latitude value;
  this audit does not silently resolve the discrepancy or perform celestial-frame
  transformations using one of them.
- **No claim made:** independent absolute pointing calibration, complete
  detector-coordinate validation, or that small coordinate residuals prove the
  fitted direction is physically correct. Real angular separations remain
  comparisons under the documented site convention.

Conference conclusion: **retain the released site coordinates and current
production timing formula; report the remaining geodetic/export limitation.**
The feared omitted blanket Earth-curvature correction is not established. The
coordinate consistency audit is complete at the level available from public
sources; precision calibration would require additional authoritative information.
