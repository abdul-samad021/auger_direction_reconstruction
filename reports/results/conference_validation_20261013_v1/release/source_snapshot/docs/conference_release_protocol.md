# Conference research release — 13 October 2026

This protocol completes the agreed scientific steps 1–11 without committing,
pushing, or opening protected validation/test events. The poster is a subsequent
deliverable, not evidence for the scientific claims. Negative and unresolved
findings are retained. No result is required to improve or attain chi-square one.

## Frozen starting evidence and population

The starting baseline is `reports/results/training_pilot_20261011_v1` plus the
previous synthetic, focus-event and pre-pilot studies. Its 711 training events
are already observed; the 145 validation and 144 test events remain sealed.
The focus event is an already unblinded example outside the pilot population.
No new real-event selection is made using protected outcomes. Baseline source,
notebooks, documents and tests are copied; all existing non-ignored research
files and result artifacts are hashed before the new analyses. All new results
go under `reports/results/conference_validation_20261013_v1`.

## Concurrent investigations and dependence order

1. Coordinate/source audit: `docs/conference_coordinate_audit.md`. Establish
   documented transformations and test invariances, distinguish approximation
   and remaining datum/export uncertainty. Counterfactual geometry changes are
   sensitivity checks, not corrections to be silently applied.
2. Instability/core study: `docs/conference_instability_protocol.md`. Freeze a
   deterministic sample from previously inspected training metrics, reproduce
   influential leave-one-out cases, examine optimization and physical geometry,
   then run fixed core perturbations. A core sensitivity scan is not a confidence
   interval. Influential stations are not automatically rejected.
3. Synthetic mismatch study: `docs/conference_stress_protocol.md`. Freeze a paired
   factorial generator/noise design before evaluating it. Distinguish actual
   timing scatter, reported uncertainty, asymmetric mean structure and noise
   skew. These are controlled stress models, not calibrated detector simulations.
4. A candidate remedy is tested only when an identified mechanism justifies it.
   It must have a written hypothesis, unchanged baseline comparison, known-truth
   controls and full failure accounting. No research remedy is promoted on
   reference agreement alone. A documented decision not to promote is a result.

## Synthesis specified before new outcomes

Existing eventwise metrics are compared with equal event weight. Full-event
metrics use 711 common events; complete conditional held-out comparisons use
466 common events and keep all 245 structurally unavailable events in the
accounting. Report paired median differences (quadratic minus plane), not the
difference of medians disguised as a paired effect. Use 2,000 seeded paired
event-bootstrap resamples and percentile 95% intervals, seed 2026101309. These
intervals describe empirical variation under resampling of this selected
training sample; they do not undo development bias or establish population
accuracy. Report median/p68/p95, adverse counts and fixed multiplicity groups.

Real-data angular separation is reference agreement, never true accuracy.
Published-core-assisted fitting and official station selection are explicit.
Fixed-core leave-one-out is conditional; its normalized MSE is not calibrated
reduced chi-square. A >1-degree influence flag is descriptive, not an exclusion.
All subgroup and paired-summary denominators are included in the outputs.

## Release gates

- Preserve and verify pre-existing evidence by hash; no overwritten old runs.
- Tests, lint and format checks pass for the integrated code.
- Independently recompute saved metrics and check signs/units/parameter bounds.
- All attempts, failures, warnings, source/configuration hashes and seeds saved.
- New figures have explicit datasets, units and comparison denominators.
- Reconcile claims with primary literature and distinguish established methods
  from this project's tested findings. Do not claim priority without evidence.
- Record unresolved physical questions, known biases and limits of inference.
- Verify that no protected raw files or run directories have appeared.
- Save a consolidated conclusion, claim ledger, reproducibility instructions,
  source snapshot and artifact manifest. No Git write operation is authorized.
