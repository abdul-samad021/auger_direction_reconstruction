# Conference coordinate audit

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

## Results

Pending protocol execution. Do not cite this draft as completed validation.
