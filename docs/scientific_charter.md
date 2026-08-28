# Scientific charter

## Primary question

Using only surface-detector station positions and timing measurements, how close
can an independently implemented plane-front reconstruction get to the arrival
direction released by the Pierre Auger Collaboration?

## Secondary question

After the physics baseline is frozen, can a machine-learning model predict a
small direction-vector correction that improves held-out angular error without
using official reconstruction outputs as inputs?

## Primary result

The main result is the distribution of angular separation between our prediction
and Auger's released SD direction on a held-out event set. Report the median,
68th percentile, 95th percentile, and failure rate, with bootstrap intervals.

## Baselines and ablations

1. Unweighted plane-front least squares.
2. Timing-uncertainty-weighted plane-front least squares.
3. Robust fit that reduces the influence of timing outliers.
4. Curved-front or ML residual correction, only after 1–3 are validated.

Test performance versus zenith, station multiplicity, energy, and detector array.

## Honest scope

- The public data are a quality-selected 10% release, not the raw detector stream.
- Station start time `t` is a calibrated estimate derived from PMT traces.
- Auger's direction is a reference reconstruction, not absolute ground truth.
- Initially relying on `isSelected` uses Auger's event-association decision; a
  later robustness check should compare an independently cleaned station set.
- A null ML improvement is a valid scientific conclusion.

## Definition of done for Phase 1

- Reproducible data provenance and cohort construction.
- Tested plane-front implementation with documented coordinate conventions.
- Frozen train/validation/test event IDs with no duplicate-event leakage.
- Quantitative results, uncertainty estimates, diagnostic plots, and limitations.
- A concise report whose claims can be reproduced from a clean environment.

