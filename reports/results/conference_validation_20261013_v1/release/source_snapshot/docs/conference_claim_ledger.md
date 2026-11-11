# Conference claim ledger — frozen research scope, 13 October 2026

Use the verified release under
`reports/results/conference_validation_20261013_v1/`, not an intermediate notebook
cell or an earlier incomplete run. This is a training/development study with
controlled simulations. It is not the completion of every future research or
deployment objective. Negative results are retained.

## Permitted claims and their evidence

| Claim | Evidence | Required qualification |
|---|---|---|
| Curvature improves timing prediction in this training cohort. | `synthesis_v2/paired_summary.csv`; 711 full comparisons, 466 complete conditional LOO pairs | Published-core assisted; station selection inherited; training-only. 245 structural LOO exclusions remain explicit. |
| Median nominal reduced chi-square falls 26.9693 to 1.5256. | Same table, timing/all_training/reduced_chi_square | Not a calibrated significance test or proof of true direction. No uncertainty rescaling was used to manufacture one. |
| Median conditional held-out timing RMS falls 366.3354 to 123.9812 ns. | Same table, 466 paired events | Fixed full-event published core: not independent end-to-end validation. Fourteen events worsen. |
| Median separation from Auger falls 1.1060 to 0.3066 degrees. | Same table, 711 paired events | Reference agreement, **not absolute angular accuracy**. Sixty-one events worsen. |
| Extreme 12.9–18.6 degree omission effects are reproducible. | `instability/all_solver_comparisons.csv`, per-event profiles/attempts | Targeted six-case study; independent numerical agreement is not a global-optimum theorem. |
| Small residuals can hide influential stations. | `instability/all_station_diagnostics.csv`; local leverage and weight shares | Association of three anchors with sat=2 does not prove faulty timing or justify rejection. |
| Core assumptions affect direction even when timing quality changes little. | `instability/all_core_sensitivities.csv` | Fixed ±50/100 m probes are sensitivity scenarios, not measured core uncertainty or confidence intervals. |
| In a chosen sparse geometry, anchor removal produces 24.795-degree p95 true error with mean nominal chi-square 0.961. | `instability/anchor_ablation/summary.csv`, `tail_numerical_audit.json` | Post-hoc mechanism experiment, chosen truth and known core, 200 paired draws/layout. Not a real-event error estimate or all-geometry rate. |
| Noise/front assumptions can reverse apparent method advantages. | `stress/final/scenario_summary.csv`, `paired_contrasts.csv` | 72 prescribed toy scenarios, not detector-level simulation. Preserve the two adverse asymmetric curvature cases. |
| No extra blanket Earth-curvature correction is justified by the audited public evidence. | `coordinates/audit_v1/summary.json`; `docs/conference_coordinate_audit.md` | Exact datum/export implementation and station-map outliers remain unresolved. Counterfactual shifts are not uncertainty bounds. |
| Results have numerical/provenance checks. | Baseline independent audit, stress independent audit, release validation/manifest | Passing tests establishes tested numerical properties, not complete physical validity. |

## Claims not supported

- "Our method is more accurate than Auger on real showers."
- "Our quadratic reconstruction is fully independent of Auger."
- "Reduced chi-square near one proves the reconstructed direction is correct."
- "All 1,000 real events were evaluated" or "the untouched test set confirms it."
- "The high-influence saturated stations are bad measurements."
- "The coordinate audit calibrates absolute pointing or resolves every survey issue."
- "We developed a new shower-front law" or "curvature/weighting is our invention."
- "The toy generators are CORSIKA plus a calibrated Auger detector simulation."
- "A neural network, validated independent core fitter or full deployment is complete."
- "A statistically favorable training result guarantees improvement on future events."

## Evaluation and promotion rules frozen for this conference version

1. Real measurements use agreement language; only synthetic truth permits true-error language.
2. Report all requested/successful/paired counts and structural exclusions. Do not drop poor fits.
3. Use equal event weighting. Report paired effects rather than subtracting unrelated medians.
4. Bootstrap intervals retain their sampling scope: selected training events or a fixed synthetic
   scenario. They do not remove training reuse, model bias or uncertainty in detector physics.
5. Full-event reference agreement cannot select core perturbations, station cuts or noise scales.
6. A candidate reconstruction needs a separately declared mechanism and validation plan before
   promotion. No remedy was justified for promotion in this conference investigation.
7. Keep existing station selection, uncertainties, coordinate inputs and fitters unchanged.
   Diagnostics explain limitations; they are not yet a calibrated quality-cut policy.
8. The 145 validation and 144 test IDs remain protected. No result in this release claims their
   performance. Opening them requires a later frozen method/evaluation decision.
9. Distinguish prespecified primary studies from the subsequently specified anchor-ablation
   mechanism check and tail audit. Never describe all follow-ups as preregistered.
10. The earlier signal/core experiment remains a documented mixed/negative result, not an
    independent core solution. The future full research scope remains in place.

## Poster emphasis

The strongest coherent story is **timing goodness-of-fit versus directional
reliability**: improvement across real training events, a reproducible influential
station case, and a known-truth experiment showing the limitation. Use that as
the central narrative, with source-backed coordinate handling and stress tests
as supporting evidence. The web demo is a later presentation/deployment task,
not additional scientific validation.
