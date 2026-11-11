# Field and leakage policy

## Measurement-level inputs allowed initially

- Station position: `stations[].x`, `y`, `z`
- Shower-front start time and uncertainty: `t`, `dt`
- Integrated signal and uncertainty: `signal`, `dsignal`
- Saturation and trace-window information: `sat`, `signalStartBin`, `signalStopBin`
- PMT traces for later feature studies: `pmt1`, `pmt2`, `pmt3`

`isSelected` may initially define which triggered stations Auger associated with
the event, but this reliance must be disclosed and later ablated.

## Targets used only for evaluation

- `sdrec.theta`, `sdrec.phi`
- Their released uncertainties, when present

Convert directions to unit vectors for fitting and angular-separation calculation.

## Quarantined from model inputs

- Official core coordinates and reconstructed event time
- Official energy and energy estimators
- Curvature radius, fit quality, and reconstruction residuals
- `stations[].spDistance` and `dspDistance`
- Official reconstructed-station collections or geometry products
- FD direction, celestial coordinates, or other independently reconstructed angles

These quantities may be used only for post-hoc stratification or diagnostics after
predictions are frozen. Every added feature requires a written leakage review.
