# EvoMem-Enterprise v3 label semantics

Version: `evomem-enterprise-v3.0.0-rc1`

This release keeps each generated task and assigns it to one of three evaluation targets before comparing retrieval methods.

## Primary current-decision target

A primary label is a minimal sufficient expected evidence set for the task answer or the declared action guards. Every listed assertion must:

1. be recorded at or before the query time;
2. be valid at that time;
3. satisfy the query's entity scope and the completed decision-relation scope;
4. satisfy lifecycle, ontology, policy-version, provenance, source, and supersession checks; and
5. survive relation-specific conflict resolution.

The set need not contain every eligible assertion in the graph. It contains the task's expected answer evidence or action witnesses. Alternative equivalent witness sets are not generated in v3 and remain a limitation.

## Historical/hindsight diagnostic target

Some inherited audit and contradiction labels identify evidence recorded after the task's historical observation time. They are retained as `retrospective` diagnostics. They test whether a method exposes hindsight records; they are excluded from the primary current-decision comparison and cannot support a retrieval-quality claim under the LGR observation contract.

## Scope-defect diagnostic target

Inherited labels whose expected assertion lies outside the declared relation or entity scope are retained as `out_of_scope` diagnostics. They are excluded from method comparisons. They remain visible in release reports and are never deleted based on a method score.

## Stage labels

- `assertion_eligible_ids`: assertions passing predicate eligibility before conflict resolution.
- `resolved_eligible_assertion_ids`: expected task evidence after conflict resolution.
- `packet_eligible_assertion_ids`: expected evidence exposed to the downstream packet.
- `eligible_assertion_ids`: the task's minimal expected resolved evidence set, retained for metric compatibility.
- `stale_or_superseded_assertion_ids`: known negative examples for temporal/lifecycle exposure metrics.
- `contradiction_winner_ids`, `expected_suppression`, and `unresolved_contradiction_ids`: conflict diagnostics, not substitutes for the minimal expected evidence set.
- `action_support_by_action`: guard witnesses for each admitted action.

Where inherited v2 records duplicate stage fields, v3 validators check their declared meaning. A future independently authored benchmark may permit multiple alternative sufficient evidence sets.

## Independence boundary

The validation-only interpreters do not import the evaluated LGR operator or generator. They still consume the same generated world, ontology, trust, policy, and workflow tables. Their agreement establishes internal consistency with those artifacts, not organizational correctness or independent human judgment.
