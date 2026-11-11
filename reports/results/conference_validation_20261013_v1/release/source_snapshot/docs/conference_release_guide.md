# Conference research release: completion and reproduction guide

Release date: **13 October 2026, America/Vancouver**. Some machine timestamps
are 14 October UTC; this is the same local evening, not inconsistent dating.

Read `reports/conference_research_conclusion.md` first, then
`docs/conference_claim_ledger.md`. The complete machine-readable evidence is
under `reports/results/conference_validation_20261013_v1/`.

## Completion of the agreed scientific tasks 1–11

| Step | Completed work | Main location |
|---:|---|---|
| 1 | Preserve the existing baseline, sources and historical results | `baseline/manifest.json`, `baseline/source_snapshot/` |
| 2 | Source-backed coordinate audit and invariance tests | `coordinates/audit_v1/`; `docs/conference_coordinate_audit.md` |
| 3 | Reproduce the extreme omission cases | `instability/selected_cases.csv`, `all_solver_comparisons.csv` |
| 4 | Distinguish numerical optimization from weak physical identification | Independent variable projection, multistart/profile/Jacobian outputs in `instability/` |
| 5 | Investigate station geometry, timing weights, residuals, signal and saturation | `instability/all_station_diagnostics.csv` and case figures |
| 6 | Quantify core dependence and retain the earlier signal-core findings | `instability/all_core_sensitivities.csv`; pre-pilot conclusion preserved |
| 7 | Complete the bounded synthetic mismatch follow-up | `stress/final/`; separate post-hoc `instability/anchor_ablation/` |
| 8 | Test/promote a remedy only if justified | No optimizer defect or validated remedy established; no arbitrary model/uncertainty/selection change promoted |
| 9 | Synthesize paired evidence, uncertainty intervals and adverse outcomes | `synthesis_v2/`, `reports/conference_research_conclusion.md` |
| 10 | Freeze scientific claims and evaluation boundaries | `docs/conference_claim_ledger.md` |
| 11 | Integrated tests, independent metric audits, reproducibility and evidence seal | `release/validation.json`, `release/manifest.json` |

This completes the agreed **conference investigation**, not the entire extended
research roadmap. The poster is the next deliverable. Independent calibrated
core/signal inference, validated selection/robustness methods, protected-split
evaluation, detector-level simulations, ML and the full app remain future work.
No Git commits or pushes were made for this release.

## Which outputs are authoritative?

- `synthesis_v2/`: final paired real-training summaries and figures. `synthesis_v1/`
  remains archived; v2 strengthened single-snapshot provenance, training-ID
  enforcement and explicit exclusions in figure labels. Numerical results did not change.
- `stress/final/`: final 72-scenario stress study. `stress/smoke/` and `stress/full/`
  are preserved verification runs, not extra independent evidence. The final
  28,800 fit records exactly match the first full run. See `stress/run_registry.json`.
- `instability/`: frozen six-case primary study. Its archived source predates the
  separately approved anchor-ablation and numerical tail-audit additions.
- `instability/anchor_ablation/`: explicitly post-hoc mechanism follow-up with
  its own source/protocol receipt. Tail-audit truth starts were only diagnostic;
  they were not passed into the original reconstruction or used to change results.
- `coordinates/audit_v1/`: source receipt, redundant-coordinate comparisons,
  mathematical invariances and deliberately counterfactual sensitivity checks.

All historical files stay unchanged. New source files and reports are additive.
The existing first-event notebook was not silently rewritten with new outcomes.
Current source gains an explicit `--output` option for fresh instability runs;
the archived source still identifies the exact original implementation.

## Useful figures for the poster

All paths below are relative to the conference result directory; PNG and SVG are
both supplied. SVG retains vector text/lines for later print-quality layout.

1. `synthesis_v2/training_paired_comparison`: real-event timing/reference comparison,
   with all complete pairs and the 245 structural held-out exclusions explicit.
2. `synthesis_v2/training_paired_intervals`: paired-effect intervals and fixed
   multiplicity groups, including empty groups rather than hiding them.
3. `instability/events/081881294400/diagnostics`: geometry, influence, objective
   profiles and core sensitivity for the largest real-event omission effect.
4. `instability/anchor_ablation/anchor_ablation`: known-truth full/omitted error
   distributions and paired effects across four fixed layouts.
5. `stress/final/stress_comparison`: matched and mismatched synthetic regimes;
   adverse effects and the fixed-grid interpretation remain visible.

These figures were visually inspected. Poster composition, final typography,
physical dimensions and print-ready PDF export are not part of this research seal.

## Reproduce without modifying frozen outputs

Run from the WSL repository root, using the project environment. Set
`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1`. Commands below
use **new output names outside the sealed release**. If they already exist,
choose another new name; do not delete or overwrite frozen evidence.

```bash
.venv/bin/python -m pytest -W error
.venv/bin/ruff check src tests scripts
.venv/bin/python scripts/freeze_conference_release.py verify

.venv/bin/python scripts/audit_training_pilot.py \
  reports/results/training_pilot_20261011_v1 \
  --output reports/results/conference_baseline_recheck_v2.json

.venv/bin/python -m auger_reco.evaluation.conference_synthesis \
  reports/results/training_pilot_20261011_v1/report/training_event_metrics.csv \
  reports/results/conference_synthesis_reproduction_v1 \
  --training-configuration reports/results/training_pilot_20261011_v1/configuration.json

.venv/bin/python -m auger_reco.evaluation.conference_stress \
  --output reports/results/conference_stress_reproduction_v1 --trials 100

.venv/bin/python -m auger_reco.evaluation.conference_instability \
  --output reports/results/conference_instability_reproduction_v1
.venv/bin/python -m auger_reco.evaluation.conference_instability \
  --output reports/results/conference_instability_reproduction_v1 --anchor-ablation
.venv/bin/python -m auger_reco.evaluation.conference_instability \
  --output reports/results/conference_instability_reproduction_v1 --audit-anchor-tails

.venv/bin/python scripts/audit_conference_coordinates.py \
  --output reports/results/conference_coordinate_reproduction_v1 \
  --notebook-archive reports/results/conference_validation_20261013_v1/coordinates/audit_v1/official_notebook.zip
```

The coordinate archive's exact saved name is verified in its source receipt.
No tutorial code is executed; it is read as source evidence. New experiment outputs record current
source hashes and may differ in machine timing metadata; compare scientific
arrays and quantities, not whole-file timestamps or SVG-generated identifiers.

The initial real-data numerical audit uses no production prediction helpers.
The independent synthetic audit is saved as
`stress/audit_stress_results.py` and its receipt as `stress/independent_audit.json`.
It recomputes all 28,800 final fits from saved parameters.

## Validation and known non-scientific advisory

The integrated suite passes **556 tests with warnings treated as errors**. The
final validation receipt records the complete warnings-as-errors test run,
repository Python lint, new-source formatting, whitespace checks, original-file
hash verification and raw filename inventory. The final manifest also covers
the new sources, reports, configurations and artifacts. Re-verification checks
both the new package and the original historical baseline.

One historical formatting-only advisory is deliberately retained:
`tests/test_event_json.py` has two line-wrap differences under the installed
formatter. It passes lint and tests and was not edited merely to remove that
notice while preserving all original files byte-for-byte. All new source files
pass formatting. This is not a scientific or execution failure.

No evidence seal can establish unmeasured detector truth. The unresolved exporter
details, training reuse, published-core assistance and toy-simulation limitations
remain scientific qualifications even when every numerical gate passes.
