# IEEE-style submission source

Compile either variant from this directory with `pdflatex -interaction=nonstopmode -halt-on-error <file>.tex`, run twice.

The author block identifies Amith Reddy Ravuru as an independent researcher in the San Francisco Bay Area. The PDF uses the IEEEtran conference class and contains native TikZ/PGFPlots vector figures; it needs no external figure files.

## Manuscript files

| File | Pages | Contents |
|---|---|---|
| `ickg_lgr.tex` / `.pdf` | Current full version | Architecture and trace figures, evaluation charts, Algorithm 1, benchmark/results tables, and references. |
| `ickg_lgr_8page.tex` / `.pdf` | 8 | **Stale — do not submit.** Retained only as a record of the earlier compressed layout. It still reports the superseded partition (78 decision-time tasks, F1 0.900 vs 0.712) and predates the action-binding, provenance, and normalization corrections. Regenerate it from `ickg_lgr.tex` before any use. |

Use `ickg_lgr.tex` and `ickg_lgr.pdf` for the current submission. Confirm the destination venue's anonymity, page-limit, and PDF-compliance rules before upload; this package does not assume an ICKG-specific limit.

## Numbers and artifacts

The manuscript reports both the preserved frozen pilot and the pre-specified
multiworld extension. Run `scripts/reproduce_lgr_release.py --force` from the
repository root before changing any pilot number. Run
`scripts/run_multiworld_experiments.py --resume --rerun-evaluation` to regenerate Phase 3 outputs, validate every world, and reconstruct
the multiworld summary. Every empirical claim traces to a saved artifact:

- Main pilot table and bootstrap intervals: `data/evomem_enterprise/phase3/metrics_test.json`, `confidence_intervals_test.json`
- Per-stratum F1 (used to explain the 0.722 aggregate): `phase3/metrics_by_task_type_test.json`
- Label-regime split behind Table I: `phase3/evidence_regimes.json`
- Masking audit and decisive counterfactual strata: `phase3/decisive_strata_report.json`
- Executable conformance: `phase3/conformance_report.json`; independent action-label cross-check: `validation/gold_action_conformance_report.json`; validation-only evidence check: `scripts/verify_evidence_labels.py`
- Multiworld protocol and results: `experiments/lgr_jws/protocol.json`, `data/evomem_enterprise_v3/worlds/multiworld_summary.json`
- Standalone composed comparator: `data/evomem_enterprise/phase3/composed_governance_report.json` and each v3 world's corresponding report
- Isolated controls: `experiments/lgr_jws/fine_grained_controls.json`
- Scaling raw timings and summaries: `experiments/lgr_jws/scaling/scaling_report.json`

Dataset construction is a separate developer workflow. The generator refuses
to overwrite a nonempty destination unless `--force` is supplied, and the
label-writing migration utility must not be used as a validator.

## Reference verification

All 31 references in the full version were checked against the published sources (title, author list, venue, year, identifier). Author lists for works with five or more authors are abbreviated with `et al.` in IEEE style, with the first author verified in each case. The 8-page variant drops five background entries co-cited with equivalent neighbours; no claim in either version depends on a removed entry.
