# Reproduce the conference reliability follow-up

This is a new evidence package, separate from the unchanged original conference
release. Start with `reports/reliability_followup_conclusion.md`; the detailed
stage reports are `reports/direction_uncertainty_conclusion.md` and
`reports/reliability_warning_conclusion.md`.

## Canonical artifacts

Root: `reports/results/conference_reliability_20261013_v1/`.

| Item | Location under root |
|---|---|
| Stage A, 4,800 fits | `stage_a/final_v2/` |
| Stage A coverage figure | `stage_a/final_v2/direction_coverage.svg` (and `.png`) |
| Stage A per-scenario results | `stage_a/final_v2/coverage_summary.csv` |
| Stage B, 3,600 development + 3,600 validation fits | `stage_b/` |
| Stage B validation figure | `stage_b/warning_validation.svg` (and `.png`) |
| Stage B policy and evaluation | `stage_b/locked_policy.json`, `stage_b/validation_summary.csv` |
| Independent numerical replay | `independent_audit.json` |
| Final source and gate receipts | `release/validation.json`, `release/manifest.json` |

The old Stage A `final/` and smoke directories are retained for provenance, not
counted as additional evidence. `final_v2` changes plotting only; the scientific
outputs are byte-identical. Stage B's archived helper predates that plot repair.
The final seal checks that no other function changed.

## Reproduce in fresh directories

From the repository root, with the existing project environment. Every study
refuses to overwrite an existing output directory. Run on one BLAS/OpenMP thread
to make runtime predictable; there is no GPU requirement for these small fits.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m auger_reco.evaluation.direction_uncertainty \
  --output reports/results/reliability_reproduction/stage_a --trials 200

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m auger_reco.evaluation.reliability_warning \
  --output reports/results/reliability_reproduction/stage_b --trials 100

.venv/bin/python scripts/audit_reliability_followup.py \
  --stage-a reports/results/reliability_reproduction/stage_a \
  --stage-b reports/results/reliability_reproduction/stage_b \
  --output reports/results/reliability_reproduction/independent_audit.json
```

Use the dedicated tests for infrastructure checks. A reduced-size command-line
run is not the canonical scientific result and can reuse the same random
streams; it is not independent evaluation. Do not select thresholds from
validation or interpret a deterministic rerun as an independent confirmation
sample. The archived development smoke and production-seed amendment are
documented separately in the Stage B protocol.

## Verify the existing frozen evidence

```bash
.venv/bin/python scripts/freeze_conference_release.py verify
.venv/bin/python scripts/freeze_reliability_followup.py verify
.venv/bin/python -m pytest -W error
.venv/bin/ruff check src tests scripts
```

The follow-up verification also checks the original release. It detects edited
or missing covered files and unexpected files inside the sealed follow-up tree.
Create a separately named study/release for future work. Do not refresh hashes
to conceal changed evidence. Historical formatter-only differences in old files
are not rewritten by this work; new Python files must pass formatting.

## Use on the poster

Prefer vector SVG figures. The primary result is the distinction among timing
fit quality, local precision and actual direction accuracy. Display the matched
case alongside adverse cases. The tested warning was **not development-viable**
and must remain explicitly **not promoted**. State the fixed-known-core,
mathematical-simulation assumptions. Real-data reference agreement is not truth.

Poster layout and printing remain a separate deliverable; these scientific
figures and conclusions are ready for that layout. No commits or pushes were
made as part of this follow-up.
