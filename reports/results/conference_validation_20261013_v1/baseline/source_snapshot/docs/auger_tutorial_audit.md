# Auger tutorial audit and verified conventions

## Purpose

This document records what the official Pierre Auger Open Data tutorials establish
for the direction-reconstruction project. It separates authoritative data semantics
from tutorial implementation shortcuts and makes the coordinate, timing, and
evaluation conventions explicit before the synthetic reconstruction is written.

The notebooks were inspected as untrusted reference files. Their source cells were
read, but their code and embedded outputs were not executed.

## 1. Source bundle and duplicate check

Twelve downloaded ZIP files were supplied:

- `notebook.zip`;
- `notebook (1).zip` through `notebook (11).zip`.

All twelve files are exact byte-for-byte duplicates:

```text
Size:   4,269,771 bytes
SHA-256: 3568191C87DACD42CE26B747C2F1AD31A084CD1D87D3F7F7E841DBCF4E6E6138
```

Only one archive therefore needs to be retained or audited. It contains seven
unique notebooks:

1. `plot_csv.ipynb`;
2. `plot_json.ipynb`;
3. `energy-calibration.ipynb`;
4. `spectrum.ipynb`;
5. `xmax_analysis.ipynb`;
6. `p-air_cross-section.ipynb`;
7. `anisotropy.ipynb`.

The weather-correction analysis listed on the Open Data analysis page is not present
in this ZIP bundle. It was supplied separately as
`weather-correction-of-the-energy-estimator.ipynb`:

```text
Size:   65,795 bytes
SHA-256: 820D1588767194D3FB37F8E05936FFEC288CB235AA87CE8E6EEE0246C8D9247D
Cells:  26
```

The seven bundled notebooks and the separately downloaded weather notebook were
all inspected. The weather notebook identifies itself with the 2021 Open Data
release, whereas the bundled notebooks use the newer release. This version
difference must be recorded if its numerical constants or fields are ever reused.

Each notebook in the ZIP bundle identifies itself as part of the Open Data release
with DOI
[`10.5281/zenodo.10488964`](https://doi.org/10.5281/zenodo.10488964). The analysis
notebooks repeatedly warn that they are simplified educational versions of the
published analyses. We will therefore use them to establish field meaning and
scientific workflow, not as production-code templates.

## 2. Verified station data semantics

The official JSON tutorial and Open Data description establish:

| Field | Meaning | Unit or role |
|---|---|---|
| `x`, `y`, `z` | Station coordinates in the Auger site system | m |
| `t` | Best estimate of the beginning of the passing shower front | ns |
| `dt` | Uncertainty in `t` | ns |
| `signal` | Integrated final station trace | VEM |
| `dsignal` | Uncertainty in integrated signal | VEM |
| `isSelected` | Station used in the official event reconstruction | 0 or 1 |
| `sat` | Saturation state of gain channels | 0, 1, or 2 |
| `pmt1`, `pmt2`, `pmt3` | PMT FADC traces | VEM; 25 ns per bin |

The public JSON is pseudo-raw. In particular, `t` is not an untouched electronic
timestamp: it is derived by analysing baseline-subtracted PMT traces and combining
the working PMTs' signal-start information.

For the first baseline:

- fit only stations with `isSelected == 1`;
- use `x`, `y`, `z`, `t`, and `dt`;
- display rejected triggers, but do not fit them;
- use signal for visualization and later diagnostics, not as a substitute for `dt`.

## 3. Verified site-coordinate orientation

Cell 32 of `plot_json.ipynb` converts event site coordinates to UTM coordinates:

$$
E=E_0+(1-\beta)x-\alpha y,
$$

$$
N=N_0+(1-\beta)y+\alpha x,
$$

$$
A=A_0+z+\frac{x^2+y^2}{2R_\oplus}.
$$

The small $\alpha$ and $\beta$ terms apply a slight rotation and scale correction;
the final term accounts for Earth's curvature in altitude. Near the site origin,
the dominant relationships are

$$
x\longleftrightarrow\text{east},
\qquad
y\longleftrightarrow\text{north},
\qquad
z\longleftrightarrow\text{up}.
$$

The constants used by the official tutorial are:

```text
E0 = 477256.66 m
N0 = 6099203.68 m
A0 = 1400 m
alpha = 2.52e-3
beta = 6.03e-4
Earth radius = 6,368,000 m
```

Our direction fit should remain in the released local site coordinates. A UTM
conversion is unnecessary for the plane fit and would only add avoidable numerical
scale and transformation complexity.

## 4. Verified direction convention

The working convention for this project is now:

- $+x$: approximately east;
- $+y$: approximately north;
- $+z$: upward;
- $\theta$: zenith angle measured from $+z$;
- $\phi$: sky-arrival azimuth measured counterclockwise from $+x$ toward $+y$;
- $\mathbf a$: unit vector pointing toward the direction in the sky from which the
  primary cosmic ray arrived;
- $\mathbf u=-\mathbf a$: downward shower-propagation vector.

Therefore, the Auger-convention sky vector is

$$
\boxed{
\mathbf a=
\left(
\sin\theta\cos\phi,
\sin\theta\sin\phi,
\cos\theta
\right)
},
$$

and the propagation vector used in the timing equation is

$$
\boxed{
\mathbf u=-\mathbf a
}.
$$

Equivalently,

$$
\phi=0^\circ\longrightarrow\text{east},
$$

$$
\phi=90^\circ\longrightarrow\text{north}.
$$

### Evidence 1: official description

The official data page describes `theta` and `phi` as the shower's **direction of
arrival** and depicts `phi` with an arrow from the reconstructed core. It separately
describes the particles as moving downward through the curved front at approximately
the speed of light.

### Evidence 2: station-timing cross-check

For event `81847956000`, a temporary two-dimensional weighted timing-gradient audit
using the 24 selected stations gives:

```text
raw u_x = -0.481996
raw u_y = -0.654153
horizontal propagation azimuth = 233.616 deg
opposite sky-arrival azimuth = 53.616 deg
official sdrec.phi = 53.760 deg
```

The opposite of the timing propagation vector agrees with the published `phi` to
about $0.14^\circ$. The published angle therefore represents the sky-arrival
direction, not the direction in which the shower front moves.

This audit calculation is not the project's final reconstruction. It uses only the
horizontal timing gradient to verify a sign and convention.

### Evidence 3: celestial-coordinate cross-check

The same event contains:

```text
UTC: 2008-07-03T10:05:59Z
right ascension: 33.26 deg
declination: 11.28 deg
official theta: 54.12 deg
official phi: 53.76 deg
```

Transforming the released right ascension and declination to the Auger site at that
time gives a zenith angle of approximately $54.10^\circ$. Its conventional
north-through-east azimuth is approximately $36.22^\circ$, which is
$90^\circ-36.22^\circ=53.78^\circ$ when expressed counterclockwise from east toward
north. This independently matches the released values.

### Coding consequence

The Day 2 temporary mathematical convention is already the Auger local sky
convention once $x$, $y$, and $z$ are interpreted as above. No extra $90^\circ$ or
$180^\circ$ correction should be inserted into the sky-vector formula. The only
required reversal is

$$
\mathbf a=-\mathbf u.
$$

Synthetic tests must include azimuths in all four quadrants so that sign swaps and
argument-order mistakes cannot pass unnoticed.

## 5. What Auger's official reconstruction does

The official data description says that the SD reconstruction:

1. estimates an initial ground core from the signal-weighted centre of selected
   stations;
2. fits selected station start times with particles moving at the speed of light in
   a curved shower front;
3. determines two directional cosines and the time the core reaches the ground;
4. fits the curvature radius `R` as a free parameter when at least five stations are
   selected;
5. proceeds to core, lateral-distribution, shower-size, and energy reconstruction.

This confirms the scientific role of our model:

- a plane front is an intentionally simpler, independently reproducible baseline;
- an explicit physical curvature model is a fair intermediate comparison;
- ML should be tested only after the plane and any justified physical correction;
- Auger's `R`, official core, `spDistance`, `geochi2`, and related quantities cannot
  be inputs to an independent baseline because they depend on the official
  reconstruction.

## 6. Notebook-by-notebook relevance

### `plot_json.ipynb` — learn now

Directly relevant material:

- JSON sections: `meta`, `info`, `flags`, `sdrec`, `stations`, and optional FD data;
- conversion of `stations` into a table;
- PMT trace spacing of 25 ns;
- selection using `isSelected`;
- joining station IDs to `sdMap.csv`;
- event site-coordinate to UTM conversion;
- footprint plots using station position, time, and signal.

Do not copy these tutorial choices into production code:

- bare `except` clauses;
- stateful notebook mutation of the `stations` table;
- silent failure when a file is not found;
- marker size `30 + signal % 100`, which uses a modulo rather than a scientifically
  interpretable signal transformation;
- hard-coded map limits;
- `spDistance` or official LDF parameters as independent direction inputs.

Our existing first-event notebook improves the visualization by using selected-only
time normalization, logarithmic signal marker sizes, grey rejected triggers, input
validation, and explicit paths.

### `plot_csv.ipynb` — learn selected parts now; use later for cohorts

Important findings:

- one summary row represents one reconstruction view, not always one unique shower;
- multi-eye hybrid events repeat the same event `id` in multiple rows;
- SD population analyses must deduplicate by `id`;
- summary fields are official reconstructed quantities, not replacements for
  station-level JSON;
- `sdMap.csv` contains UTM station positions, operating intervals, and array flags;
- exposure files contain cumulative exposure normalized to the released 10% sample;
- event IDs encode the Auger day, which begins at noon UTC;
- GPS time and civil timestamps differ because GPS time does not include leap
  seconds.

For our project, the summary CSV selects and stratifies the event cohort and stores
evaluation references. Detailed direction fitting still requires each event's JSON.

### `energy-calibration.ipynb` — read later as a statistical pattern

Useful general lessons:

- analysis-specific quality flags define scientifically different cohorts;
- multi-eye estimates are combined before applying the final energy cut;
- repeated measurements are combined with inverse-variance weights;
- statistical measurement uncertainty and shower-to-shower fluctuations are
  separate contributions;
- an easy curve fit can initialize a more appropriate likelihood fit.

Its `sd_s38`, energy, official zenith, weather, geomagnetic, core, and FD fields are
not inputs to our independent direction baseline.

### `spectrum.ipynb` — reference for population analysis

Useful later when describing the analysed population:

- vertical SD-1500 events use $\theta<60^\circ$;
- the full-efficiency threshold discussed for that population is $2.5$ EeV;
- inclined events and SD-750 events are separate samples with different thresholds;
- duplicated event IDs must be removed before counting showers;
- exposure and energy-bin width are required for a physical flux;
- sparse counts require Poisson intervals rather than symmetric Gaussian error bars;
- an upward fluctuation in a 10% release is not automatically physical evidence.

We are not measuring the cosmic-ray energy spectrum in this project. The notebook is
a methodological reference for cohort definition, small-sample caution, and
uncertainty reporting.

### `xmax_analysis.ipynb` — reference for uncertainty and bias analysis

Useful general lessons:

- merge multi-eye measurements with inverse-variance weighting;
- distinguish measurement uncertainty from physical shower-to-shower variation;
- define bins before inspecting final trends;
- report statistical and systematic uncertainty separately;
- detector resolution broadens an observed distribution;
- detector acceptance can bias distribution tails even after quality selection;
- compare observations with multiple physical models rather than one preferred
  simulation.

The notebook concerns fluorescence-detector composition measurements, not SD timing
direction reconstruction.

### `p-air_cross-section.ipynb` — reference only

Useful methodological lessons:

- select a scientifically motivated distribution region before fitting;
- include acceptance directly in a likelihood model;
- check explicitly for duplicate events;
- use profile likelihood for asymmetric uncertainty;
- propagate model dependence separately from statistical uncertainty;
- state omitted systematic uncertainties.

No code or fields from this analysis are needed for the initial direction fitter.

### `anisotropy.ipynb` — important later, not for the first fit

Useful later when reconstructed directions are studied on the sky:

- the summary CSV already provides equatorial and Galactic coordinates;
- spherical maps require exposure correction;
- HEALPix uses colatitude rather than astronomical latitude;
- astronomical sky maps often reverse the displayed longitude axis;
- `atan2` is used for harmonic phase for the same quadrant reason discussed on Day
  2;
- the released 10% sample has reduced statistical significance;
- the simplified example omits small exposure nonuniformities and array tilt.

This notebook must not be used to train or validate the station-level direction fit.
It consumes directions that have already been officially reconstructed.

### `weather-correction-of-the-energy-estimator.ipynb` — later systematic-effects reference

This notebook joins the cosmic-ray summary table to a weather-station time series
and reproduces Auger's tabulated energy-estimator weather correction. Its physical
model is

$$
S=S_0\left[
1+\alpha_P(P-P_0)
+\alpha_\rho(\rho_d-\rho_0)
+\beta_\rho(\widetilde{\rho}-\rho_d)
\right],
$$

where $P$ is event-time pressure, $\rho_d$ is the daily mean density,
$\widetilde{\rho}$ is the density two hours earlier, and $P_0$ and $\rho_0$ are
site reference conditions. The coefficients vary with $\sin^2\theta$. The notebook
interpolates weather measurements to an event time, calculates the multiplicative
correction, and checks it against the released `sd_wcorr` value.

Useful methodological lessons are:

- environmental conditions can act as nuisance variables rather than primary
  physics signals;
- a correction should be defined relative to explicit reference conditions;
- external time-series data must be aligned to event times before joining;
- a reimplementation should be checked against a released reference value;
- applying a correction and proving that it improves a measurement are separate
  tasks.

It is not part of the timing-only direction baseline. In particular, the tutorial's
correction function takes the already reconstructed `sd_theta`, so copying it into
our pre-fit pipeline would leak Auger's answer. Weather quantities may be considered
later as post-fit diagnostic metadata, or in a separately justified systematic
study using our own reconstructed zenith. `sd_wcorr` remains an evaluation/reference
field, not a model input.

Do not copy these tutorial simplifications into production code:

- a single hard-coded GPS--UTC leap-second offset for the full historical sample;
- interpolation without explicit coverage, missing-value, or extrapolation checks;
- hard-coded coefficients without version provenance or uncertainty propagation;
- implicit physical units in variable names;
- reliance on official zenith while evaluating an independent direction method.

## 7. What to read now

The student does not need to read all eight notebooks. Before synthetic coding, the
high-value source cells are:

### `plot_json.ipynb`

- Cells 6–12: file loading and JSON sections;
- Cells 20 and 23: event/station interpretation and PMT bin timing;
- Cells 26–32: footprint, `isSelected`, detector map, and coordinate conversion.

### `plot_csv.ipynb`

- Cells 10 and 13–18: why multi-eye rows duplicate physical event IDs;
- Cells 29–31: SD/hybrid selection and the meaning of official reconstructed fields;
- Cells 44–50: site and UTM maps;
- Cells 63–71: auxiliary station map and exposure-file semantics.

### Official data description

Read only the sections describing:

- how station start and stop times are obtained;
- how the official curved-front direction reconstruction begins;
- the station-field table;
- the distinction between JSON event measurements and CSV summaries.

The remaining notebooks can stay as later reference material.

### Weather notebook — defer until systematic studies

There is no required reading from this notebook before the synthetic direction
exercise. If atmospheric systematics later become relevant, read cells 14--21 for
the physical correction model and cells 22--25 for its one-event reference check.

## 8. Production-code standards derived from the audit

Our implementation will not imitate the notebooks cell for cell. It will use:

- `pathlib.Path` and explicit, validated paths;
- context-managed file and archive access;
- schema and finite-value validation;
- explicit units in names and documentation;
- immutable or copied input tables rather than hidden in-place mutation;
- typed return objects for vectors, residuals, metrics, and failure status;
- focused functions in `src/auger_reco/` rather than notebook-only logic;
- deterministic cohort manifests and event-ID deduplication;
- QR/SVD least-squares solvers rather than explicit matrix inversion;
- explicit optimizer convergence and geometry checks;
- tests for every quadrant, sign convention, units, noise, and degenerate geometry;
- no bare `except` clauses or silently missing data;
- notebooks as explanations and experiments, not the authoritative implementation;
- quarantined official reconstruction fields until evaluation.

## 9. Input and evaluation boundary

| Category | Fields or examples | Project role |
|---|---|---|
| Baseline inputs | Auger-selected `x`, `y`, `z`, `t`, `dt` | Independently implemented fit with Auger-assisted station selection |
| Diagnostics | `signal`, `dsignal`, `sat`, rejected triggers | Plots and later justified features |
| Evaluation reference | official `theta`, `phi`, `ra`, `dec` | Reveal after prediction |
| Evaluation metadata | official energy, multiplicity, quality fields, external weather variables | Post-fit stratification and systematic checks |
| Prohibited baseline inputs | official core, `R`, `spDistance`, `sd_wcorr`, official fit quality, official direction-derived fields | Leakage |

## 10. Consequence for the synthetic exercise

The manual-verification phase resolved the convention used by the synthetic
reconstruction. That implementation was required to:

1. define station coordinates in the Auger site system;
2. choose a known Auger sky direction $(\theta,\phi)$;
3. calculate $\mathbf a$ with the verified sky-vector formula;
4. set $\mathbf u=-\mathbf a$ for downward propagation;
5. generate station times from $t_i=t_0+\mathbf u\cdot\mathbf r_i/c$;
6. recover the direction without passing the chosen answer into the fitter;
7. test exact, noisy, vertical, four-quadrant, and degenerate cases;
8. compare using unit-vector angular separation.

The completed convention check remains the reference for production and real-event
integration. No extra azimuth rotation or propagation/arrival sign swap should be
introduced later.

## Authoritative references

- [Pierre Auger Open Data description](https://opendata.auger.org/data.php)
- [Pierre Auger Open Data analysis examples](https://opendata.auger.org/analysis.php)
- [Open Data release DOI 10.5281/zenodo.10488964](https://doi.org/10.5281/zenodo.10488964)
