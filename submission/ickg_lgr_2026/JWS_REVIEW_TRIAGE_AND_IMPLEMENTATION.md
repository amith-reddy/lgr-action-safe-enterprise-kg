# JWS review triage and implementation brief

Assessment date: 2026-09-05. Paths below are relative to the repository root.

This document evaluates the eight recommendations supplied by the author and
served as the implementation specification. The automated portions were
implemented and verified on 2026-09-05; tasks requiring an external contributor,
public-upload authorization, or an author-selected license remain open.

## Implementation status

- Ground truth: generator conflict labels now use declared authority, record
  time, unresolved incompatible ties, and equivalent-value ties; five semantic
  regression tests pass. Version-3 label semantics are frozen separately from
  the historical release.
- Validation: evidence and action checkers are separately implemented,
  read-only, hash their inputs, report exact failures, and detect deliberate
  evidence, verdict, witness, and reason corruptions.
- Multiworld evaluation: 3 development, 2 validation, and 10 test worlds were
  retained under the frozen protocol. The test population contains 743 primary
  tasks; the validation-selected contrast is $+0.215$ eligible F1 with a
  world-bootstrap 95% interval of $[+0.212,+0.218]$.
- Comparator: the standalone custom governance composition matches LGR evidence
  on 1,500/1,500 tasks and table-derived actions on 635/635 action tasks. The
  manuscript therefore claims equivalence on tested cases, not superiority.
- Controls: seven additional decisive cases isolate record visibility, valid
  time, provenance activity, source eligibility, workflow-instance scope,
  conflict trust, and action-target binding; all pass.
- Scaling: 180 raw measurements cover 1,000, 10,000, and 100,000 assertions in
  unrelated-growth and dense-neighborhood modes. The manuscript reports p50/p95
  without extrapolating to a production graph store.
- Reproduction and packaging: the frozen-release reproduction preserves all
  input hashes. A 1,127-entry archive passes clean-extraction manifest checking
  and reproduces the frozen results.
- External validation: the scenario protocol and blank labeling template exist,
  but no independently authored cases are claimed.
- Still open: code/data license choice, public repository or archival deposit,
  and an independently authored or real-LLM evaluation.

## Evidence checked

- `scripts/verify_evidence_labels.py`: passes; 75 permitted, 22 retrospective, and 3 out-of-scope frozen test tasks; no failure in the permitted group.
- `scripts/verify_gold_labels.py`: passes on 60 action labels across smoke, development, and test splits. Only 40 are frozen test action labels.
- `python3 -m unittest discover -s tests -p test_lgr_conformance.py`: all 34 tests pass.
- Current frozen labels: `t_00022` uses `a_00527`; `t_00029` uses `a_00485`. Both are the later CRM assertions identified in the earlier review. The generator's `relationship_aware_retrieval` branch now selects a later visible owner assertion rather than always using its original construction-time pointer.
- Eight baseline retrieval methods plus LGR and eight ablations already exist in `scripts/run_phase3_experiments.py`.
- The manuscript already discloses one generated world, post-hoc subgroup selection, common action gating, masked ablations, and ten decisive cases. Its current headline is 0.963 F1 versus 0.741 on 75 tasks. Those metric values were read from the manuscript, not independently recomputed in this review.
- The current README no longer recommends submitting the old eight-page version, and REPRODUCIBILITY.md now reports 34 tests and 75 permitted tasks.

Passing these checks does not establish full semantic coverage of either checker. A clean regeneration and full metric rerun were not performed here.

## General implementation rules

1. Preserve the existing release and its results. New datasets belong in a new versioned directory; never overwrite the current world during experiment development.
2. Keep the abstract and Sections I–II locked under the author's standing instruction. If new evidence requires a factual correction there, provide a proposed patch separately and identify the affected claim.
3. Implement one task below at a time. Report changed paths, verification command, actual outcome, and remaining limitations. Do not silently broaden scope.
4. Validators must read labels and fail on disagreement. Label generation or repair must be a separate, explicit operation with a change manifest.
5. Do not tune labels, exclusion criteria, comparator choices, or seed inclusion to make LGR win. A valid experiment may show equality or a disadvantage.
6. Do not describe automated or AI review as independent human annotation. Maintain the distinction between independently written code and independently authored scenarios.
7. Build the PDF after every manuscript change. This review changes only this implementation brief, so no paper PDF rebuild is required for it.

## 1. Resolve and freeze ground truth

**Decision: the two named unresolved-label complaints are outdated. Accept reproducible freezing and broader label repair as follow-up work.**

The named labels already have the expected IDs, and their correction appears in generator logic. Repeating that repair would be unnecessary. The larger concern is still valid: 22 retrospective labels and 3 out-of-scope labels remain unsuitable for the current primary decision-time evaluation. They are disclosed, but partitioning the old release does not produce a clean prospective test set.

**Task 1A — Add semantic regression fixtures.**

Files: `scripts/generate_evomem_enterprise.py`, new `tests/test_gold_generation.py`.

- Add tiny scenarios for higher authority versus later time, equal authority with later time, equal authority/time with incompatible values, and equivalent top assertions.
- Test expected answer content as well as evidence IDs and conflict reasons. IDs must never resolve an incompatible tie.
- Inspect the generator's owner branch, which currently ranks candidate IDs by record time and ID. Its restricted candidate construction works for the two observed cases; new worlds need the general declared trust/time/tie semantics.
- Keep this generator implementation separate from production resolver code.

Pass condition: fixtures satisfy the written contract, including an unresolved outcome for incompatible top ties. The two old task expectations remain regression checks, not task-specific conditionals in generation code.

**Task 1B — Define new-release label semantics.**

Files: new `data/evomem_enterprise_v3/LABELING_SPEC.md`, generator and schemas.

- Define the target for each task family before evaluating methods: current admissible evidence, historical evidence as known at a stated time, or explicitly identified hindsight evidence.
- Review the intended question behind each of the 22 retrospective tasks. Do not automatically advance its query time to make its label pass. If the intended answer concerns hindsight, give it a distinct target and metric; otherwise construct its expected answer from evidence available then.
- Review the three scope defects against the question text. Correct either the scope or expected evidence based on intended meaning, with a task-level rationale.
- Specify whether evidence labels are exhaustive relevant sets, minimal sufficient witnesses, or alternative acceptable sets. Eligibility alone does not make every surviving assertion relevant, and one witness set may not be unique.
- Distinguish pre-conflict eligible evidence, resolved evidence, packet evidence, stale items, conflict losers, unresolved components, and action witnesses. Do not assign the same set to every stage merely for convenience.
- Emit a migration manifest recording old/new labels, task changes, semantic reason, and source release hashes. Preserve every original task in the historical release.

Pass condition: every primary new-release task has a well-defined, satisfiable target under its declared mode; no task is dropped because of a method score. All label fields agree with that target.

## 2. Strengthen independent label validation

**Decision: valid coverage concern; the suggestion to create a separate checker from scratch is outdated. Mandatory manual review of every label is excessive for deterministic checks.**

Both validators already import neither generator nor evaluated operator. However, `verify_evidence_labels.py` uses a fixed alias dictionary, exact ontology-version equality, raw query scope, and a membership check over listed gold IDs. It does not fully implement the manuscript's mapping semantics, completed guard scope, or label completeness. Its regime classification also suppresses failure reporting for a task with any retrospective/out-of-scope reason, potentially hiding additional defects. `verify_gold_labels.py` computes actions using the supplied gold evidence; its passing result is conditional on that evidence being complete and valid.

**Task 2A — Extend the existing evidence validator.**

Files: `scripts/verify_evidence_labels.py`, new `tests/test_evidence_validator.py`.

- Read versioned ontology and conflict configuration instead of relying only on fixed aliases and version equality.
- Implement the documented identity/rewrite/split rules, ambiguity handling, canonical conflict keys, trust precedence, top-time ties, and multi-value exceptions independently.
- Distinguish retrieval scope from completed decision-evidence scope. Validate the correct target for each label field.
- Implement mode-specific lifecycle/supersession semantics and explicit handling of malformed timestamps and disallowed sources.
- Check missing, duplicate, extraneous, and omitted required evidence according to Task 1B's target definition. A subset-membership check must not be called completeness verification.
- Report every task's reasons even when the task belongs to a non-primary regime. Treat an expected retrospective status separately from unrelated label errors.
- Check stale, loser, unresolved, witness, and stage labels where they contribute to reported metrics or manuscript claims.

**Task 2B — Check the action validator's assumptions.**

Files: `scripts/verify_gold_labels.py`, new `tests/test_label_validators.py`.

- Consume independently verified decision evidence or derive it through the independent reference semantics; do not let incomplete supplied gold silently dictate the expected action.
- Add fixtures for missing evidence, critical unresolved conflicts, target isolation, historical query mode, missing registration/binding, deny precedence, and ambiguous mappings.
- Corrupt one evidence ID, one action verdict, one witness, and one label reason in separate temporary fixtures. Each relevant validator must detect the corruption.
- Maintain no-write behavior and nonzero exit codes for real mismatches. Emit structured reports with checker version, input hashes, counts by split, and exact failures.

Pass condition: independently specified positive and negative fixtures pass, deliberate corruptions are detected, and every claimed field has a test. Agreement with production code alone is not the pass criterion.

Human work: ask a qualified reviewer to assess the labeling rubric and representative ambiguous cases if available. Record actual review and disagreement resolution. Until then, describe results as independently implemented consistency checks under shared scenario assumptions.

## 3. Evaluate multiple generated worlds

**Decision: valid and high value. Reject “at least ten” as an established minimum or journal rule. Ten test worlds is a proposed practical starting point.**

The generator currently has hard-coded seeds and a fixed output directory. Other pipeline scripts also hard-code the data path. Editing `config/seeds.yaml` alone is not enough: generation reads module constants. A changed task shuffle or renamed entity IDs is not a new world.

**Task 3A — Parameterize the pipeline.**

Files: generator; provenance builder; structural validator; label generator; both label validators; experiment runner; regime reporter; decisive-case runner; result validator.

- Introduce explicit `--data-root`/`--output-dir` arguments as applicable and `--seed`/`--config` for generation. Pass paths into functions instead of rewriting module globals during experiments.
- Refuse to overwrite a nonempty dataset destination by default.
- Derive separate entity/event/contradiction/task/split RNG streams deterministically from the master seed using a stable algorithm; avoid Python's process-dependent `hash()`.
- Generate actual differences in facts, histories, conflicts, and workflows. Namespace all linked entity, assertion, workflow, and task IDs by world.
- Parameterize conflict rate, tie frequency, provenance failures, version transitions, supersession depth, and workflow branching where supported. Add generator fixtures for every new mechanism.

Pass condition: repeated generation with the same seed/config produces identical semantic file hashes; different seeds produce different semantic scenarios; paths and identifiers never leak across worlds.

**Task 3B — Freeze an experiment protocol.**

New files: `experiments/lgr_jws/protocol.json`, `scripts/run_multiworld_experiments.py`, `scripts/summarize_multiworld_results.py`.

- Suggested budget: 3 development worlds, 2 validation worlds, 10 frozen test worlds with approximately 100 primary tasks each. These are planning defaults, not a power guarantee. Confirm feasible runtime on development worlds first.
- Separate same-configuration random variation from deliberate structural stress configurations. Report them separately.
- Fix seeds, task mix, budgets, comparators, metrics, exclusion rules, and uncertainty calculation before viewing test outcomes. Choose the primary comparator on validation worlds.
- Validate every world's labels before method evaluation. Log generator failures and retries under an explicit rule; never silently discard a difficult world.
- Store every method/task/world result. Compute each world's macro score, then report an equal-weight mean and sample standard deviation across worlds.
- For the primary contrast, calculate paired per-world differences and a bootstrap interval by resampling worlds, keeping all paired method observations together. Record the bootstrap seed and resample count; show individual world differences and note instability with few worlds.
- Publish all predefined test worlds, including negative outcomes. If test inspection triggers a substantive fix, record it and establish a new untouched test evaluation.

Pass condition: independent world IDs, reproducible manifests, no split leakage, and a summary that reconstructs exactly from per-world rows. Claim consistency across seeds only if the observed results support it; shared generator assumptions remain a limitation.

## 4. Add fair baselines

**Decision: mostly existing work. Accept a stronger composed comparator and information-access audit. Reject recreating the listed baselines.**

The current method list already covers lexical top-k, recency, TTL, temporal, provenance, ontology, graph expansion, and latest-state retrieval. The review incorrectly called the first baseline vector retrieval: it is lexical. A real embedding baseline would be new work. The manuscript already identifies these as local variants, not reproductions of published GraphRAG systems.

All main methods currently invoke the same `evaluate_lgr` action gate over the full snapshot. Their equal action scores cannot measure relative admission quality. LGR also builds retrieval context from completed evidence; sharing k alone does not establish equal preprocessing or candidate access.

**Task 4A — Write and enforce an information-access matrix.**

Files: experiment runner; new `experiments/lgr_jws/baseline_protocol.md`.

- For every method, record snapshot access, candidate pool, ontology mappings, trust tables, policy/workflow access, dependency completion, ranking, k, witness additions, and runtime boundary.
- Match available raw information and account for each method's preprocessing. For an operator-only comparison, use identical precomputed candidates; for a retrieval comparison, allow documented candidate-generation differences.
- Audit whether witness insertion can exceed k. Enforce the same context rule or explicitly report additional witness cost for every method.
- Keep the shared-gate comparison labeled as a retrieval comparison. Retain the equal action score as a control result.

**Task 4B — Implement one defensible composed system.**

New file: `scripts/composed_governance_baseline.py` plus fixtures.

- Define the comparator as a separate implementation of temporal/version/provenance filtering, declared conflict handling, and policy/workflow evaluation using the same input tables.
- If claiming SHACL/XACML execution, run actual pinned engines and document the translation. A Python imitation must be named a custom composition.
- Specify missing-witness behavior, ties, action binding, and dependency access before test evaluation. Do not deliberately omit ordinary correctness checks to manufacture superiority.
- Evaluate standalone end-to-end output, including decisions and reasons, without routing it through LGR's final gate. Also compare evidence and overhead under matched conditions.
- If outputs agree, report equivalence on tested cases and compare specification clarity, trace completeness, or cost only with explicit measurements. This result can narrow novelty to integration and formalization.

Pass condition: same input information, no gold access, reproducible configuration, transparent implementation differences, and claims matching the actual comparator. Real GraphRAG/HippoRAG/other system runs remain necessary only for empirical superiority claims about those systems.

## 5. Expand ablations

**Decision: useful refinement; most ablations already exist. Reject the assumption that every removal must degrade every aggregate metric.**

Current flags combine provenance with source trust, validity with record visibility, and workflow-related binding behavior. These combinations limit attribution. Ten existing decisive cases cover lifecycle, supersession, and policy-version cases, not every proposed mechanism.

**Task 5A — Split mechanisms without changing default behavior.**

Files: `scripts/lgr_operator.py`, `scripts/run_phase3_experiments.py`, conformance tests.

- Separate validity-interval and record-visibility controls, provenance and source-membership controls, and action-target binding and workflow-guard controls.
- State whether trust ablation disables source eligibility, conflict ranking, or both. Give them separate experiments if making separate claims.
- Preserve old combined flags only as documented compatibility aliases. Assert default behavior remains equivalent on existing fixtures.
- Record exact active controls in every result row.

**Task 5B — Add decisive fixtures and conditional metrics.**

Files: `scripts/run_decisive_strata.py`, new fixture data/tests.

- Reuse existing cases. Add at least one sole-failure fixture and one passing control for every newly isolated mechanism.
- Include ontology ambiguity, valid cross-version mapping, absent provenance, undeclared source, invisible future record, expired interval, and missing workflow guard as separate causes.
- Assert the full system's reason set, the ablation's evidence change, and an action change only when the removed condition actually decides that action.
- Report exposure on relevant negative cases, eligible recall, invalid admission rate, and false-denial rate with explicit numerators/denominators. Distinguish empty-set cases from meaningful perfect suppression.
- For synthetic stress mixtures, fix mixture weights in advance and disclose them. Report zero or positive ablation changes honestly.
- An optional permissive fallback must define exactly which missing witness is waived. Keep it confined to offline evaluation and label it a deliberately weakened control; it is not a production mode or competitive baseline.

Pass condition: each isolated change is demonstrably caused by the named control in its decisive fixture, and aggregate results retain all predefined cases. Replace the review's phrase “unauthorized action matches” with “invalid admissions”; a match normally means agreement with gold.

## 6. Add scalability evidence

**Decision: valid for an implemented systems contribution; proposed graph sizes are illustrative. Storage-neutrality does not itself imply scalability.**

**Task 6 — Build a standalone performance harness.**

New file: `scripts/benchmark_lgr_scaling.py`; output under `experiments/lgr_jws/scaling/`.

- Start with roughly 1,000, 10,000, and 100,000 assertions. Attempt one million only after a development run establishes feasibility. Publish resource limits and failed runs.
- Measure both growth in unrelated graph records and growth in the queried dependency/conflict neighborhood. Mere duplication of irrelevant records is an incomplete scaling study.
- Generate coherent unique IDs and valid links. Validate labels and invariants at every size.
- Separate loading, snapshot digest, index construction (if any), dependency completion, eligibility, conflict resolution, admission, serialization, and total wall time. If no index exists, report that rather than inventing an index cost.
- Record machine/OS/Python version, CPU, memory, seed, graph size, candidate and closure sizes, conflict statistics, and packet bytes.
- Proposed initial measurement budget: 20 warm-up queries and at least 200 measured queries per size per seed, using fixed query sets across methods. Report cold-start cost separately; use separate processes for peak resident-memory measurement.
- Report p50/p95 from raw timings and their sample count. Keep instrumentation outside the timed region where possible. Define what is cached.

Pass condition: raw timings reconstruct the summary, stage accounting is explicit, and any performance claim names the tested implementation and hardware. Do not hash latency files as deterministic outputs.

## 7. Release a public artifact

**Decision: valid reproducibility objective; reject “GitHub alone is insufficient” and “Zenodo DOI is mandatory” as universal rules. No such JWS requirement was verified in this review.**

Local scripts and documentation already exist. Public availability and a DOI were not established. The unrelated `toposwe/LICENSE` must not be treated as a license for LGR.

**Task 7A — Separate reproduction from benchmark construction.**

Files: `submission/ickg_lgr_2026/REPRODUCIBILITY.md`, README; new `scripts/reproduce_lgr_release.py`.

- The current instructions begin by generating data and rewriting labels. Add a primary reproduction command that starts from frozen inputs, verifies hashes, runs validation/evaluation, and writes results to a new directory.
- Put regeneration and label migration in a separate developer workflow. Neither may silently update the reference labels during verification.
- Declare the Python version and only dependencies actually needed. A container is optional if a clean environment reproduces the work.
- Include schemas, configs, labels, seeds, validators, tests, raw outputs needed for figures, and exact figure/table generation commands.
- Add release-specific code/data licensing after the author selects applicable licenses, citation metadata, version, and a data-availability statement.
- Hash canonical inputs and deterministic outputs; record runtime statistics separately. Record the commit or source archive hash.

**Task 7B — Prepare an archive for publication.**

- Build a release archive and verify its contents in an empty temporary directory with the documented command.
- Prepare GitHub/Zenodo metadata and a proposed tag. A permanent version DOI is recommended for citation and preservation.
- Actual public upload requires the author's authorization; do not invent a DOI or claim release before it exists.

Pass condition: a clean extraction reproduces semantic outputs without mutating reference inputs, documentation matches actual commands, and every manuscript figure/table has a traceable source.

## 8. Improve external validity

**Decision: valid optional strengthening. A public temporal KG with invented governance does not become an enterprise authorization benchmark.**

**Task 8 — Prepare an independently authored scenario protocol.**

New files: `experiments/lgr_jws/external_scenarios/protocol.md` and a blank labeling template.

- Suggested pilot: 20–30 cases across two documented policy/workflow families, including permitted, denied, missing-witness, and unresolved-conflict cases. This is a budget proposal, not a statistical threshold.
- Ask a qualified contributor to write the scenarios and expected outcomes from source documents without seeing LGR outputs. Record sources, assumptions, annotation rationale, and actual reviewer identity/role with consent.
- Separate source facts from newly authored mappings, trust orders, and policies. Label each synthetic addition explicitly.
- If using a public temporal KG, evaluate temporal retrieval on its supported task; evaluate authored governance separately. Do not claim the original dataset validates the invented authorization layer.
- If an AI model authors scenarios, describe them as model-generated additional scenarios, not human/external validation.
- Freeze cases before operator evaluation and report all outcomes and adjudications. Human participants or restricted data require the relevant permissions.

Pass condition: traceable origins independent of the original generator, frozen expectations, transparent synthetic additions, and a claim limited to the tested scenarios. If no external contributor/data is available, retain this limitation.

## Execution order and claim gates

1. Tasks 1A–1B: ground-truth semantics and regression coverage.
2. Tasks 2A–2B: validator coverage and negative fixtures.
3. Task 3A and 7A: isolated data paths and reliable reproduction.
4. Tasks 4A–4B and 5A–5B: comparator and decisive mechanisms developed on development worlds.
5. Task 3B: freeze the protocol, then execute untouched test worlds.
6. Task 6: scaling measurements; Task 8 when independent inputs are available.
7. Task 7B: release packaging; synchronize manuscript, documentation, figures, and PDF from actual results.

Correctness of labels, accurate claims, and reproducibility are submission integrity requirements. Ten worlds, one million assertions, a specific comparator engine, human review of every deterministic label, and a Zenodo DOI are not verified mandatory JWS requirements. Multiworld evaluation and a serious composed comparator are the strongest recommended scientific additions.

Automated closure gates: no validator imports production/generator functions; expected fixture outcomes verified; frozen input hashes unchanged; no failed world omitted; reported values generated from saved results; compiled paper matches the release. Automated gates cannot certify organizational policy correctness, independent human review, novelty, or journal acceptance.

## Venue source and scope boundary

The official call for “Multi-dimensional Knowledge Graphs and Multi-perspective Ontologies” covers provenance, validity intervals, conflicting viewpoints, ontology patterns, and performant querying. That supports topical relevance. It does not establish acceptance likelihood, novelty, or the experiment thresholds suggested here.

Source: https://www.journals.elsevier.com/journal-of-web-semantics/call-for-papers (search-indexed official content checked 2026-09-05; direct page retrieval returned HTTP 403).

## Patch to locked Section I (author-approved; applied)

Filed under General implementation rule 2: a factual correction was required in a
locked section, so it was proposed here first. **The author approved it and it is
now applied to `ickg_lgr.tex`.** This is the only change made to the abstract or
Sections I--II; everything else in the locked region is byte-for-byte unchanged
from `rc1`.

**Affected claim.** Section I (Introduction), motivating example:

> The first two are documented, not hypothetical: in *Moffatt v. Air Canada* the
> B.C. Civil Resolution Tribunal held an airline liable after its chatbot
> answered a refund question with conditions contradicting the applicable
> bereavement-fare policy.

**Why it is wrong.** The sentence attributes the first two of the three listed
cases -- a superseded entitlement, and an SLA tier drawn from the wrong policy
version -- to the cited incident. The tribunal decision establishes liability for
chatbot-supplied information contradicting a fare policy. It does not establish
either of those two mechanisms: nothing in it turns on a superseded record or on
a stale policy version. The citation is real and correctly described in its own
right; only the "the first two are documented" bridge overstates what it
supports.

**Proposed replacement** (the preceding and following sentences are unchanged):

> A related real-world failure illustrates the consequences of
> policy-inconsistent assistance: in *Moffatt v. Air Canada* the B.C. Civil
> Resolution Tribunal held an airline liable after its chatbot answered a refund
> question with conditions contradicting the applicable bereavement-fare policy
> \cite{aircanada}.

This keeps the citation and the motivation while dropping the mechanism claim.

**Related, same section, also approved and applied.** `KG` (contributions list)
and `SLA` (motivating example) are first used in Section I. Both are now expanded
there on first use -- "knowledge graph (KG)" and "service-level agreement (SLA)".
The interim expansions previously added at the first editable occurrence
(Sections III and IV) were reverted, so each acronym is defined exactly once, at
its true first use.
