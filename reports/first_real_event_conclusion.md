# First real-event reconstruction: scientific conclusion

For event **081847956000**, both constrained plane-front fits converged using
**24 of 28 triggered stations**, with station selection inherited from Auger's
`isSelected` flag. This event is an **unblinded development example**, not a
protected test.

| Quantity | Timing-weighted | Uniform |
|---|---:|---:|
| Angular separation from Auger reference | 0.263904° | 0.377055° |
| Reduced chi-square (21 nominal degrees of freedom) | 72.930514 | 287.662360 |
| Unweighted timing-residual RMS | 462.776 ns | 338.501 ns |

The weighted fit is closer to the reference for this event but has a larger
unweighted RMS. This is consistent with the different fitting objectives:
the weighted fit minimizes uncertainty-scaled squared residuals, whereas the
uniform fit minimizes raw squared residuals. Reference agreement is **not**
an error measurement against the unknown true direction.

The weighted total chi-square is **1531.541**. Stations **203, 814, and 548**
contribute **46.1%** of that total. Several central stations have negative timing
residuals, while many outer stations have positive residuals. This qualitative
spatial structure motivates testing curvature and other timing-model
assumptions; it neither identifies the shower core nor demonstrates the cause
of the mismatch.

All **24 leave-one-station-out refits** succeeded. The median direction change
relative to the full fit was **0.175274°**, with a maximum of **0.450408°** when
station **203** was omitted. Retained-set reduced chi-square remained between
**57.5655 and 76.4758**: no single omission resolved the timing mismatch.
Contribution and directional-influence rankings differ.

**Limitations.** These are single-event diagnostics, not population accuracy
or calibrated directional uncertainties. The baseline and leave-one-out fits
carry the `surface_like_geometry` quality flag. Large residual contributions
are not independent station-level significance tests. Omission changes both
the dataset and degrees of freedom; a lower reduced chi-square is not sufficient
grounds for rejection or a claim of improved direction accuracy. Curvature,
uncertainty miscalibration, and detector/timing effects remain hypotheses.

**Next experiments.** Broaden paired weighted-versus-uniform synthetic tests
across direction, geometry, and multiplicity; inject controlled curvature; and
validate a curvature-aware fitter initially with a known synthetic core.
Then compare on a fixed 10–20-event development sample. Advance to the frozen
1,000-event pilot with target separation and preserved development/validation/test
roles; freeze analysis choices before opening protected test references.
No curvature correction, uncertainty rescaling, or new station rejection
was introduced in this diagnostic baseline.
