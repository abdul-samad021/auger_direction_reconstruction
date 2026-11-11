# Research publication and historical provenance

The accumulated research was published in focused commits on 10 November 2026.
The experiments and conference reports retain their original October dates.
Publishing them does not imply that the full research roadmap is complete or
that machine learning, protected-real-cohort evaluation, or deployment is done.

## What this publication contains

- Current reconstruction, data-adapter, evaluation and audit source code.
- The executable test suite and explanatory notebooks.
- Research protocols, conclusions, adverse outcomes and run registries.
- A reviewed subset of canonical scientific tables, figures, configurations,
  original source snapshots and historical verification receipts.

See [the evidence index](../reports/README.md). The generated
[publication manifest](../reports/published_results_manifest.json) identifies
the included result files by their original path, size and SHA-256 hash.
This is an inventory of the publication, not a replacement scientific seal.

## What remains local

The complete run archives remain unchanged on the research machine. Git excludes
bulk optimizer logs and numerical arrays, per-event checkpoints, duplicate or
interrupted runs, notebook copies, raw station-measurement tables and the
downloaded third-party tutorial archive. Nothing was deleted to publish this
compact evidence set. Complete downloaded Auger event files and bulk measurement
tables are not redistributed; explanatory notebooks retain small displayed
subsets. Obtain full inputs from the official source under their original terms.

This checkout is therefore not the complete historical evidence bundle. Some
older reports and receipts refer to files retained only in the full local
archives. Consult the relevant protocol and run into a new output directory
when reproducing an experiment; do not overwrite a frozen run.

## Historical integrity checks versus a new Git commit

The original release checks intentionally bind both artifact contents and the
Git HEAD that existed when the experiment was frozen. Legitimate publication
commits change HEAD. A historical seal can consequently fail its HEAD-equality
check even when all original scientific artifact bytes are unchanged.

The original manifests, hashes and source snapshots have not been rewritten or
resealed to disguise this distinction. Full historical verification additionally
requires the files omitted from this compact checkout. Do not interpret a
published historical receipt as a fresh verification of the publication commit.

For the current source checkout, run the software checks from the README. The
publication process also tested an isolated archive of the committed source,
without the local untracked run archives: all 746 tests passed. This validates
the tested software contracts, not complete detector accuracy or every
historical scientific output.

## Scientific reading order

Use the current README and [conference conclusion](../reports/conference_research_conclusion.md)
for overall status. Older pre-pilot reports describe the project at their run
dates, not the present status. The [14 October frame correction](../reports/exported_direction_frame_conclusion.md)
supersedes historical mixed-frame reference-angle comparisons; timing results
and known-truth synthetic results are unaffected. Protected real validation and
test outcomes remain unopened. A synthetic validation experiment is not an
evaluation of those reserved real-event cohorts.
