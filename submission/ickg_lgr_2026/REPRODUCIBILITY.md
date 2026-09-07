# Reproducibility and conformance workflow

The primary reproduction path starts from the frozen release, writes every
recomputed result to a separate directory, and verifies that no frozen input
changed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/reproduce_lgr_release.py --force
```

This command was executed with Python 3.9.6 on 2026-09-05. It completed all
seven validation/evaluation stages and recorded
`source_inputs_unchanged: true` in
`experiments/lgr_reproduction/reproduction_report.json`.

The complete conformance and robustness workflow is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_evomem_enterprise.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_gold_labels.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_evidence_labels.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_phase3_experiments.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/report_evidence_regimes.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_lgr_conformance tests.test_gold_generation tests.test_label_validators tests.test_composed_governance -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_lgr_conformance.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_decisive_strata.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_fine_grained_controls.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/composed_governance_baseline.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_phase3_results.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_multiworld_experiments.py --resume --rerun-evaluation
PYTHONDONTWRITEBYTECODE=1 python3 scripts/benchmark_lgr_scaling.py
```

Frozen pilot artifacts live under `data/evomem_enterprise/`. Versioned
multiworld data live under `data/evomem_enterprise_v3/worlds/`; their frozen
protocol is `experiments/lgr_jws/protocol.json` and their summary is
`data/evomem_enterprise_v3/worlds/multiworld_summary.json`. The baseline
information-access contract is `experiments/lgr_jws/baseline_protocol.md`.
Fine-grained controls and scaling measurements are under
`experiments/lgr_jws/`.

## Benchmark construction and migration

Generation is intentionally separate from reproduction. A new destination is
required unless `--force` is explicitly supplied:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_evomem_enterprise.py \
  --output-dir data/evomem_enterprise_v3/worlds/example \
  --master-seed 34001 --world-id example --benchmark-version 3.0.0
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_provenance_registry.py \
  --data-root data/evomem_enterprise_v3/worlds/example
```

`rederive_evomem_gold.py` is a label-writing migration utility and is never
used as evidence that its own labels are correct. The two validation-only
checkers are read-only and import neither the generator nor the evaluated
operator.

## Metric definitions (Section IV-A of the manuscript)

Evidence metrics (eligible precision/recall/F1, stale non-exposure, loser non-exposure) are computed over the eight-item initial retrieval context and macro-averaged. The decision boundary separately completes the declared query, guard, conflict, and supersession dependencies from the immutable snapshot before applying the common table-driven gate, so action-set agreement is a gate-conformance result, not an initial-retriever advantage. `k = 8` is fixed because no gold evidence set exceeds four assertions.

**Label regimes.** `report_evidence_regimes.py` computes the time-and-scope partition, and `verify_evidence_labels.py` independently checks that each label in the permitted group also survives the released eligibility and conflict rules. Together they report 75 *permitted* tasks, 22 *retrospective* tasks (14 audit, 8 of 14 contradiction) that require evidence recorded afterwards, and 3 tasks whose evidence lies outside the query scope. The regimes are reported separately because their macro-average is a target no single retrieval behaviour can maximize. Comparison baselines are whichever implemented method is strongest per metric, with none excluded.

## Conformance evidence

`tests/test_lgr_conformance.py` holds 34 cases over 29 declared requirement areas. Twenty-three additional tests exercise generator conflict semantics, label-validator mutations, and the standalone comparator, giving 57 passing tests in total. Five of these were added for the `rc2` corrections: paired tests that the composed comparator and the action-label interpreter each reject workflow membership declared by an untrusted source while still admitting membership a trusted record declares, and a mutation test that deleting a contradiction task's unique-winner answer from every duplicated stage field is detected. Thirteen operator cases exercise admission properties the frozen split cannot express:

| Property | Counterexample |
|---|---|
| Guard witnesses bound to one action target | With two accounts in scope, the gate admitted the first account's refund using the second account's subscription status |
| Action target must resolve | Multi-principal scope evaluated against a mixture instead of being refused |
| Completed dependencies survive eligibility | Narrowing the retrieval scope discarded a workflow guard witness and changed the admitted set |
| Query mode | A historical query admitted effectful actions |
| Split-mapping ambiguity | The same assertion normalized to different variables depending on relation-scope order |
| Renaming classes | A renamed relation split one decision variable in two |
| Provenance references | A dangling or source-mismatched provenance citation passed eligibility |
| Temporal fields | A malformed or timezone-less timestamp read as an open interval boundary |
| Deterministic decision record | Replay compared the operator return value, not the record; rule/transition identities were not recorded |

Correcting all of these left every reported number unchanged, because this benchmark's action tasks each carry one coherent case, none is retrospective, and no released mapping is ambiguous.

The seven-control report independently toggles record visibility, valid time,
provenance-activity resolution, source eligibility, workflow-instance scope,
relation-specific trust precedence, and action-target binding. Each constructed
case passes and identifies its exact active flag. These are decisive
counterexamples, not population estimates.

The aggregate ablation table uses the same isolated flags. Two additional rows
are explicitly labeled interactions: `lgr_no_bitemporal_checks` disables both
record-time visibility and valid time, while
`lgr_no_workflow_scope_or_target_binding` disables both workflow-instance scope
and action-target binding. Effects from those rows are not attributed to either
individual control.

**Label verification is separate from label generation.** `rederive_evomem_gold.py` *writes* labels back into the benchmark and so cannot witness its own output. `verify_evidence_labels.py` independently derives contract-permitted evidence from the assertion snapshot, checks all stage-label views, rejects malformed timestamps, detects required-answer omissions, and reports the 75/22/3 regimes. `verify_gold_labels.py` uses that independently derived evidence rather than supplied gold evidence to re-derive all 60 action labels, including target binding and critical-conflict blocking. Both import neither the evaluated operator nor the generator, write nothing, and exit non-zero on disagreement.

**Provenance registry.** `build_provenance_registry.py` emits `generated/provenance_activities.jsonl`, the declared activity registry `ProvOK` resolves against. It is held apart from the assertion stream so a citation cannot vouch for itself, and it is covered by the snapshot digest.

## Scope

The multiworld protocol evaluates 10 untouched test worlds after comparator
selection on two validation worlds. It retains every generated world and
resamples worlds, not tasks, for the primary confidence interval. All worlds
still share one generator family. The separately implemented custom governance
composition reproduces the LGR evidence result on 1,500 method/world tasks and
the table-derived action result on 635 action tasks. Its separate regression cases also reject cross-target witnesses and unresolved critical conflicts; this is evidence of
implementability and equivalence on the tested cases, not superiority over
published systems.

These checks cover the stated branches of the reference implementation.
Passing them is not proof of organizational policy correctness, production
safety, durable distributed storage, independently authored scenarios, or
real-LLM effectiveness.
