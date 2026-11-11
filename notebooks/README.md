# Notebooks

Use notebooks for short-lived exploration and explanatory figures. Move parsing,
physics, evaluation, and plotting functions into `src/auger_reco/` as soon as they
are reused. A notebook should call tested functions rather than become the only
place where a scientific result can be reproduced.

## Reconstruction and validation sequence

1. `01_explore_first_event.ipynb` — inspect the first event and its station data.
2. `02_reconstruct_synthetic_shower.ipynb` — learn and validate plane-front
   reconstruction on exact and noisy synthetic timings.
3. `03_reconstruct_first_real_event.ipynb` — reconstruct the development event and
   investigate its timing residuals against a published reconstruction reference.
4. `04_benchmark_synthetic_plane_front.ipynb` — broaden paired timing-weighted versus
   uniform plane fits across directions, layouts, and station counts.
5. `05_benchmark_curved_front.ipynb` — compare plane and **known-core** quadratic
   fits on controlled curvature, including the zero-curvature control, core-offset
   sensitivity, and a translating spherical-cap mismatch test.
6. `06_compare_real_event_front_models.ipynb` — compare plane and **Auger-core-assisted**
   quadratic fits for the previously examined event and 19 preselected training
   events. Includes conditional leave-one-station-out timing predictions and core
   sensitivity; preserves reference disagreement and cases without improvement.
7. `07_pre_pilot_diagnostics.ipynb` — fixed-reference-direction profiles, station
   influence, independent spherical and coherent-timing-bias controls, and an
   experimental signal-based horizontal core estimate with slope sensitivity and
   held-out refitting. Saves a target-free pilot execution list and a baseline-only
   analysis contract; does not start the pilot or promote the signal estimator.

Run each notebook from a fresh project-environment kernel, in cell order. Notebook
05 calls the tested `physics/quadratic_front.py` timing generator and
`physics/curved_front.py` fitter; it leaves `physics/plane_front.py` unchanged.
It creates a new timestamped directory under `reports/results/` with the frozen
configuration, source snapshots, inputs, noise, optimizer attempts, fit metrics,
paired summaries, figures, and a scientific conclusion.

**14 October direction-frame integration:** notebooks 03 and 06 now load a
site-frame evaluation reference using the shared `data/direction_reference.py`
adapter. Notebook 07 calls the corrected pre-pilot routines, including the
explicitly reference-assisted fixed-direction diagnostic. Published angles
remain labeled core-local; fitted angles remain site-local. Stale affected
comparison outputs have been cleared rather than relabeled. Restart the kernel
and run in order to populate new outputs in a new run directory. Historical
results are not overwritten; see `docs/direction_frame_integration.md`.

Only runs whose `run_status.json` says `complete` should be used for interpretation.
Known-core synthetic recovery is not independent core estimation, a full detector
simulation, or evidence that the real-event chi-square has been resolved.

Notebook 06 uses the frozen `real_front_development_v1.json` manifest. Its 19
additional events belong only to the pilot's train split and have at least seven
officially selected stations. See `docs/real_front_comparison_protocol.md` for the
sampling rule, information dependencies, and reporting requirements. The fixed
core comes from Auger's released `sdrec.x/y/z`, separately from the direction-blind
timing adapter. Held-out predictions remain conditional on Auger's full-event core
and station selection, not independent end-to-end cross-validation. The notebook
does not download data automatically or fit protected validation/test events.

## Checkpointed training pilot after Notebook 07

The 711-event training run is executed by the tested
`auger_reco.evaluation.pilot_batch` module, rather than a long-running notebook
cell. Its per-event checkpoints support interruption recovery. Validation and
test events remain sealed. Read
[`reports/training_pilot_conclusion.md`](../reports/training_pilot_conclusion.md)
for the completed results and
[`docs/training_pilot_execution.md`](../docs/training_pilot_execution.md) for
reproduction, auditing and reporting. The authoritative run is recorded in
`reports/training_pilot_run_registry.json`; this batch uses terminal event
outcomes and invocation receipts rather than the earlier notebook
`run_status.json` convention.
