# Frozen pilot: training-only execution

This stage executes the already frozen **plane versus published-core-assisted
quadratic** comparison. It is not a deployment, a final test-set evaluation, or
a claim of true-direction accuracy. No commit is made automatically.

## Population and model contract

- Use the target-free execution manifest from
  `reports/results/prepilot_diagnostics_20261010T234353_804166Z/`.
- Its 1,000 events contain **711 training, 145 validation, and 144 test** events.
  Only the 711 training events may be downloaded, fitted, or evaluated here.
- The previously examined focus event is not in the frozen population. Do not
  append it. Identify the 19 previously examined training events separately.
- Retain the frozen options, official station selection, physical timing
  uncertainties, and unmodified released Cartesian coordinates.
- Fit plane and quadratic models with both timing and uniform weighting. The
  quadratic model uses the published core; the experimental signal/core model
  is **not promoted** to this baseline comparison.
- Perform all leave-one-station-out (LOO) attempts. Do not run additional
  core-offset probes in this batch. There are `4 + 4*N` fit attempts per valid
  event. Six-station events retain explicit quadratic LOO failures because only
  five stations remain and the frozen quadratic minimum is six.
- Never rescale uncertainties or remove stations merely to obtain a reduced
  chi-square near one. A large value is a diagnostic to investigate.

## Execution and recovery

Run from the WSL repository, with its existing environment:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m auger_reco.evaluation.pilot_batch \
  --run-dir reports/results/training_pilot_RUN_ID --workers 2 --max-events 2
```

The first invocation is a two-event operational smoke test, not a scientific
subsample. Continue in **the same directory**, with exactly the same source and
environment, omitting `--max-events` to process every remaining training event.
The limit controls work per invocation; it does not redefine the population.

The runner uses a process-lifetime single-writer lock. For each authorized event:

1. Download or validate the existing raw JSON, then record its hash and receipt.
2. Load only station measurements and the separate published-core adapter.
3. Fit all full-data and LOO configurations, retaining every attempted fit.
4. Atomically persist a hash-sealed prediction checkpoint.
5. Only then load and compare the published direction; persist this evaluation.
6. Persist a terminal outcome bound to the preceding checkpoint hashes.

An interruption resumes from its last complete checkpoint. Terminal download,
input, and reference failures are retained, not retried automatically. A retry
requires an explicitly documented new run/attempt; never erase the failure.
Unexpected programming errors abort, rather than being converted into a
plausible scientific failure. Changes to source, versions, configuration, raw
data, or checkpoint contents block resume. Source snapshots accompany each run.
Undefined/nonfinite optimizer diagnostics are exported as JSON `null` with an
explicit field-location ledger, not nonstandard JSON NaN/Infinity values.

## Interpretation and reporting

Report every configured event, data failure, full-fit failure, failed LOO fold,
and quality flag. Numerical convergence does not establish scientific validity.
The one-degree LOO influence warning is informational, never an exclusion cut.

First aggregate held-out station residuals **within each event**. Compare event
metrics with equal event weight; do not pool all stations into one distribution.
For paired plane/quadratic LOO comparisons, require every fold to succeed for
both methods. State both the complete-pair count and the incomplete count.
Report median, 68th and 95th percentiles with metric-specific denominators and
station-multiplicity groups. Record previous-development versus remaining
training subsets without presenting either as independent test data.

The held-out normalized mean-square residual divides only by the released
measurement uncertainty. It is neither a reduced chi-square nor a predictive
pull including fit-parameter, core, or model uncertainty. LOO remains conditional
on the fixed official core and station selection, which used the event data;
it is not independent end-to-end validation. Uniform fits minimize unweighted
timing squares, even though their diagnostic chi-square uses physical sigmas.

Reduced timing mismatch and improved agreement with Auger are separate outcomes.
Auger directions are reconstructed references, not known true directions. Keep
protected splits sealed until the complete analysis procedure is frozen. Any
training-driven improvements belong in a separately documented next experiment.

## Independent checks and additional figures

After all training event outcomes exist, independently recompute every successful
fit's residual metrics from its saved direction and curvature, check every planned
full/LOO attempt, verify all raw/source/checkpoint hashes, and recompute reference
separations using a separate vector formula:

```bash
.venv/bin/python scripts/audit_training_pilot.py \
  reports/results/training_pilot_RUN_ID \
  --output reports/results/training_pilot_RUN_ID/independent_audit.json
.venv/bin/python scripts/plot_training_pilot.py \
  reports/results/training_pilot_RUN_ID
```

The audit checks internal numerical consistency, not true physical accuracy. Its
receipt and the extra figures refuse to overwrite existing outputs. The additional
logarithmic-axis figures use the frozen report's same complete pairs and retain
extreme tails; they do not alter eligibility, fit options, or primary summaries.
