# Real-event core-assisted curvature comparison

Run: real_front_comparison_20261010T201113_597655Z

## Focus event: timing-weighted fits

| Model | Nominal reduced chi-square | RMS residual (ns) | Separation from Auger (deg) |
|---|---:|---:|---:|
| plane | 72.9305 | 462.776 | 0.263897 |
| quadratic | 4.6522 | 96.714 | 0.551962 |

Fitted quadratic delay at 1 km: 100.2313 ns.

Conditional held-out RMS: 491.193 ns (plane) versus 114.812 ns (quadratic); 24/24 paired folds.

## Additional preselected training events

- Selected: 19; complete timing-weighted full-fit pairs: 19.
- Lower quadratic nominal reduced chi-square: 19/19 pairs with finite diagnostics.
- Closer quadratic direction to Auger: 17/19 pairs.
- Lower quadratic conditional held-out normalized MSE: 17/19 events with all station folds paired.
- Event loading/comparison failures: 0/20.
- Failed fit records: 0/1072; all retained in the saved tables.

## Interpretation and limits

The comparison tests a specific fixed-core quadratic timing approximation, not the full Auger reconstruction. The core and station selection are inherited from Auger. Reference-direction separation is not error against known truth. Conditional held-out timing predictions reuse that full-event core and selection and are not independent end-to-end cross-validation. Their normalized MSE is not reduced chi-square.

Core offsets are sensitivity probes, not confidence regions. A smaller residual objective is expected for a nested flexible model and does not alone establish more accurate directions. Remaining timing mismatch can reflect front shape, uncertainty calibration, detector effects or coordinate-system limitations; this study does not uniquely identify their causes. No uncertainty rescaling or additional station rejection was used.

The focus event is excluded from the 19-event aggregate. Results are descriptive for a small, selected development sample, not population accuracy. Validation/test event fits were not performed. Preserve the plane baseline and do not advance to protected test evaluation until the method and analysis choices are frozen.
