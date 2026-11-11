# Automatic published-direction frame alignment

## What changed

The frame correction is implemented in the current source, not just described
in a report or left as an optional postprocessing instruction.

1. Fit the released station measurements in their central-site Cartesian frame.
2. Save the prediction before loading Auger's published direction.
3. Load the published core-local sky angles and the core's UTM easting/northing.
4. Rotate that reference vector into central-site ENU automatically.
5. Calculate angular separation between two vectors in that same frame and
   save the transformation provenance with the comparison.

The implementation is `src/auger_reco/data/direction_reference.py`, using locked
`pyproj==3.7.2` and the WGS84 UTM zone 19 south CRS. The core's location identifies
the reference basis; it does not become a new input to the blind plane fit.
Altitude is not needed for the basis rotation. No Earth-sag correction, constant
angle offset, uncertainty inflation, or change to timing model parameters occurs.

The method version is `auger-core-enu-to-site-enu-wgs84-v1`. Invalid/missing core
coordinates fail explicitly; there is no fallback to the old mixed-frame result.
Native published angles and angular uncertainties are preserved. No covariance
rotation is claimed because the released marginal uncertainties do not define a
full covariance matrix.

## Entry points

- Notebook 03: first-event comparison, with native and common-frame labels.
- Notebook 06: paired real-event plane/quadratic comparisons.
- Notebook 07 / `prepilot_study.py`: both the explicitly reference-assisted
  fixed-direction profile and signal-core diagnostic comparisons.
- `pilot_batch.py`: reference conversion occurs after the saved-prediction barrier;
  versioned checkpoints prevent silent reuse of legacy comparisons.
- `pilot_reporting.py`, `conference_synthesis.py`, and plotting/audit scripts:
  frame-version checks prevent mixing historical and corrected reference metrics.

Generic angle/vector functions remain unchanged: they are valid within a single
specified frame. `event_json.load_auger_direction_reference` deliberately still
returns native published angles. New real-data comparisons must use
`direction_reference.load_auger_site_direction_reference` instead of treating
those native angles as a site-frame vector.

## Safe use

From the project root:

```bash
uv sync --inexact
uv run pytest -W error
```

Restart notebook kernels before running updated cells. Affected old comparison
outputs were cleared; frozen result files and fit outputs were not overwritten.
Run notebooks in order with a new run directory. New batch work likewise uses a
new directory. Resuming historical frame-unversioned checkpoints is rejected,
not silently upgraded and not silently refitted.

The `--allow-legacy-reference-frame` switch is solely for reproducing labeled
historical comparisons, not for obtaining corrected results. Mixing corrected
and legacy frame versions in one reference summary is rejected. Never reuse
historical angle confidence intervals as though their inputs had been corrected.

## Verification and unchanged evidence

`scripts/verify_direction_frame_integration.py` compares the production loader
with the independently verified frozen audit for all **2,848 comparisons** from
**711 already-observed training events plus one focus event**. Its first receipt
is `reports/direction_frame_integration_check_20261014.json`. Maximum separation
difference was **7.83e-15 degrees**, with an absolute numerical tolerance of
1e-10 degrees. This is a regression tolerance, not detector resolution.

The check hashes the saved audit artifacts and raw inputs, opens no protected
validation/test event, and executes no fits. Existing timing residuals,
chi-square, conditional held-out timing, within-event direction shifts, and
synthetic truth results from the free-direction baseline fits are unchanged.
The explicitly **fixed-reference-direction** diagnostic is different: correcting
the direction held fixed changes its conditional timing profile on a future
rerun. Historical fixed-direction diagnostic outputs have not been recalculated
or relabeled; they must not be presented as frame-corrected profiles.
Empirical redundant-field evidence for
the export convention is documented in `conference_coordinate_audit.md`; this
is not exporter-source inspection or an absolute-pointing calibration.

Final integration validation: **746 tests passed with warnings treated as
errors**, repository Python lint passed, the dependency lock is current, and
tracked changes pass the whitespace check. Tests execute the updated notebook
comparison cells against synthetic displaced-core fixtures; the long real-event
notebooks and historical fixed-reference experiments were not rerun wholesale.

The authoritative corrected conference comparison numbers remain:

| Timing-weighted result | Corrected separation from Auger |
|---|---:|
| Focus event, plane | 0.310355 degrees |
| Focus event, quadratic | 0.522484 degrees |
| 711-event plane median | 1.077334 degrees |
| 711-event quadratic median | 0.255079 degrees |

Quadratic is farther from the reference in **43/711** timing-weighted cases.
These measure reference agreement, not known-truth angular accuracy.
