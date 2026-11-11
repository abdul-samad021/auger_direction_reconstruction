# Published research evidence

This index accompanies the November 2026 publication of the completed conference
study. Start with the conclusions, then inspect the supporting canonical tables
and figures. The [publication manifest](published_results_manifest.json) lists
the exact result files included in Git, with original paths and SHA-256 hashes.

| Study | Scientific interpretation | Published result directory |
|---|---|---|
| Synthetic plane benchmarks | Paired comparisons across prescribed layouts, directions and noise | [Notebook 04 run](results/synthetic_plane_benchmark_20261010T104612_802216Z/) |
| Controlled curvature | [Conclusion and limitations](controlled_curvature_conclusion.md) | [Conclusion run](results/synthetic_curvature_20261010T111048_941039Z/), [current notebook run](results/synthetic_curvature_20261010T190421_183127Z/) |
| First real-event diagnostics | [Initial conclusion](first_real_event_conclusion.md) | [Notebook 03 run](results/event_081847956000_run_20261010T100751_894864Z/) |
| Real-front comparison | [Development comparison](real_front_comparison_conclusion.md) | [Registered run](results/real_front_comparison_20261010T201113_597655Z/), [later audited run](results/real_front_comparison_20261010T204030_242582Z/) |
| Core/signal prototype | [Pre-pilot conclusion](prepilot_diagnostics_conclusion.md) | [Canonical run](results/prepilot_diagnostics_20261010T234353_804166Z/) |
| 711-event development cohort | [Historical pilot conclusion](training_pilot_conclusion.md) | [Tables and figures](results/training_pilot_20261011_v1/report/) |
| Robustness and instability | [Conference synthesis](conference_research_conclusion.md), [instability](conference_instability_conclusion.md), [stress tests](conference_stress_conclusion.md) | [Conference evidence](results/conference_validation_20261013_v1/) |
| Direction uncertainty and warning rule | [Follow-up conclusion](reliability_followup_conclusion.md) | [Coverage](results/conference_reliability_20261013_v1/stage_a/final_v2/), [warning evaluation](results/conference_reliability_20261013_v1/stage_b/) |
| Corrected reference directions | [Frame audit and correction](exported_direction_frame_conclusion.md) | [Authoritative corrected comparisons](results/exported_direction_frame_20261014_v2/) |

## Interpretation boundaries

- Real-event results are development-stage and use published-core assistance
  for the curved model. Auger's reconstructed direction is a reference, not truth.
- Reference-angle numbers in older run tables may use a legacy mixed frame.
  Use the corrected comparison directory above for current reference claims.
- More than one archived run can be linked because notebooks and reports record
  different execution times. Reruns are not additional independent evidence.
- The signal-core prototype and diagnostic warning were not promoted. Their
  negative results remain part of the study.
- A figure or receipt does not imply that all of its underlying bulk files are
  distributed in Git. This is a compact, explicitly partial publication of the
  complete local archives.

See [publication notes](../docs/publication_notes.md) for omitted artifacts,
reproduction boundaries and the distinction between original Git-HEAD-bound
integrity seals and the later publication commits. No historical outputs were
modified or deleted for this publication.
