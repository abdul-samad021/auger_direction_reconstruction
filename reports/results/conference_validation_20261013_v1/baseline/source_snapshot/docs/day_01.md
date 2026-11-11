# Day 1 checklist

Status: completed. Event `081847956000` is an unblinded schema, visualization, and
coordinate-convention example; it is not a blinded reconstruction result.

## Goal

Turn one official event into a trusted local object and be able to explain every
field that the first direction reconstruction will use.

## Steps

- [x] Create the environment with `uv sync`.
- [x] List configured sources with `uv run auger sources`.
- [x] Download and checksum the documented event.
- [x] Run structural and physical-consistency validation.
- [x] Inspect the event summary and selected-station count.
- [x] Open the JSON and identify `info`, `flags`, `sdrec`, and `stations`.
- [x] Explain why `sdrec.theta` and `sdrec.phi` are targets, not features.
- [x] Confirm the units and Auger coordinate/azimuth convention before fitting.

## Questions to answer in your own words

1. Why do relative station times contain the shower direction?
2. Why do we need multiple stations spread over the ground?
3. Why is event `081847956000` good for debugging but bad as a final sample?
4. What information would leak Auger's answer into our model?
5. What would make a downloaded file scientifically trustworthy?
