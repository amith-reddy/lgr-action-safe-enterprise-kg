#!/usr/bin/env python3
"""Validation-only check that frozen evidence labels obey the LGR contract.

The checker imports neither the benchmark generator nor the evaluated LGR
operator.  It reads the frozen assertion stream and governance tables, applies
the released eligibility and conflict rules independently, and fails when a
decision-time gold assertion would be suppressed.  Retrospective and
out-of-scope labels are counted separately because the manuscript reports them
as intentionally unsatisfiable regimes rather than permitted evidence.
"""

from __future__ import annotations

import json
import argparse
from datetime import datetime
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"

# Task types whose answer is carried by the evidence label itself, so an empty or
# incomplete label is a contract violation rather than a legitimately empty case.
EVIDENCE_ANSWER_TASK_TYPES = {
    "current_factual_recall",
    "relationship_aware_retrieval",
    "contradiction_handling",
    "audit_valid_historical_explanation",
}
# Task types that must exhibit an answer for every relation in scope. A
# contradiction-handling task instead must exhibit a winner for every relation
# that is actually contradicted; an audit explanation is only required to be
# non-empty, since its answer is the surviving history rather than one relation.
ALL_RELATIONS_REQUIRED_TASK_TYPES = {
    "current_factual_recall",
    "relationship_aware_retrieval",
}

ALIASES = {
    "support_plan": "support_entitlement",
    "entitlement_profile": "support_entitlement",
    "owner": "account_owner",
    "refund_status": "workflow_state",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def malformed_temporal_fields(row: dict, fields: tuple[str, ...]) -> list[str]:
    """Return populated timestamp fields that are not timezone-aware ISO-8601."""
    errors = []
    for field in fields:
        value = row.get(field)
        if value not in (None, "") and parse_time(value) is None:
            errors.append(field)
    return errors


def canonical(relation: str | None) -> str | None:
    return ALIASES.get(relation, relation)


def query_time(task: dict) -> datetime | None:
    field = "audit_time" if task.get("retrieval_mode") == "audit_historical" else "decision_time"
    return parse_time(task.get(field))


def mapping_targets(predicate: str, source_version: str, target_version: str, mappings: list[dict]) -> set[str]:
    frontier = {(source_version, predicate)}
    visited: set[tuple[str, str]] = set()
    targets: set[str] = set()
    while frontier:
        version, relation = frontier.pop()
        if (version, relation) in visited:
            continue
        visited.add((version, relation))
        if version == target_version:
            targets.add(canonical(relation))
            continue
        for item in mappings:
            if item.get("from_ov") == version and item.get("from_relation") == relation:
                frontier.add((item.get("to_ov"), item.get("to_relation")))
    return {value for value in targets if value}


def normalized_candidates(row: dict, task: dict, mappings: list[dict]) -> set[str]:
    predicate, source, target = row.get("predicate"), row.get("ontology_version"), task.get("target_ontology_version")
    if not predicate or not source or not target:
        return set()
    targets = mapping_targets(predicate, source, target, mappings)
    if source == target:
        targets.add(canonical(predicate))
    return targets


def guard_relations(expression: dict | None) -> set[str]:
    if not expression:
        return set()
    if "and" in expression:
        return set().union(*(guard_relations(item) for item in expression["and"]))
    for operator in ("equals", "not_equals", "in"):
        if operator in expression:
            return {canonical(expression[operator][0])}
    if "exists" in expression:
        return {canonical(expression["exists"])}
    return set()


def decision_relations(task: dict, registry: dict, policies: dict[str, list[dict]], workflows: dict[str, dict]) -> set[str]:
    relations = {canonical(value) for value in task.get("relation_scope") or []}
    for action in task.get("candidate_actions") or []:
        registration = registry.get(action)
        if not registration:
            continue
        for rule in policies.get(task.get("target_policy_version"), []):
            if rule.get("action") == action and rule.get("policy_family") == registration.get("policy_family"):
                relations |= guard_relations(rule.get("guard"))
        workflow = workflows.get(registration.get("workflow_type"))
        if workflow:
            relations.add("workflow_state")
            for transition in workflow.get("transitions", []):
                if transition.get("action") == action:
                    relations |= guard_relations(transition.get("guard"))
    return {value for value in relations if value}


def covers_scope(row: dict, task: dict, mappings: list[dict], allowed_relations: set[str]) -> tuple[bool, bool]:
    candidates = normalized_candidates(row, task, mappings)
    relation_ok = len(candidates) == 1 and next(iter(candidates)) in allowed_relations
    entities = set(task.get("entity_scope") or [])
    entity_ok = (
        row.get("subject") in entities
        or bool(entities & set(row.get("entity_scope") or []))
        or bool(task.get("workflow_instance_id") and row.get("workflow_instance_id") == task.get("workflow_instance_id"))
    )
    return relation_ok, entity_ok


def base_reasons(
    row: dict,
    task: dict,
    assertions: dict[str, dict],
    activities: dict[str, dict],
    trust: dict[str, list[str]],
    mappings: list[dict],
    allowed_relations: set[str],
) -> list[str]:
    reasons: list[str] = []
    when = query_time(task)
    recorded = parse_time(row.get("record_time"))
    if when is None or recorded is None or recorded > when:
        reasons.append("recorded_after_query")
    start, end = parse_time(row.get("valid_from")), parse_time(row.get("valid_until"))
    if when is None or (start and when < start) or (end and not when < end):
        reasons.append("outside_validity_interval")
    mode = task.get("retrieval_mode", "current_action")
    state = row.get("lifecycle_state")
    if (mode == "current_action" and state != "active") or (mode == "audit_historical" and state in {"deleted", "retracted"}):
        reasons.append("inactive_lifecycle")
    candidates = normalized_candidates(row, task, mappings)
    if not candidates:
        reasons.append("ontology_version_mismatch")
    elif len(candidates) > 1:
        reasons.append("ontology_ambiguous")
    if row.get("assertion_type") in {"policy_fact", "action_permission", "workflow_policy_binding"}:
        if row.get("policy_version") != task.get("target_policy_version"):
            reasons.append("policy_version_mismatch")
    relation = next(iter(candidates)) if len(candidates) == 1 else canonical(row.get("predicate"))
    tiers = trust.get(relation, [])
    if row.get("source") not in tiers:
        reasons.append("source_not_declared")
    activity = activities.get(row.get("provenance_activity"))
    if activity is None or activity.get("source") != row.get("source"):
        reasons.append("invalid_provenance")
    if row.get("source") in set(task.get("disallowed_sources") or []):
        reasons.append("source_disallowed")
    relation_ok, entity_ok = covers_scope(row, task, mappings, allowed_relations)
    if not relation_ok:
        reasons.append("relation_out_of_scope")
    if not entity_ok:
        reasons.append("entity_out_of_scope")
    if mode == "current_action" and any(
        successor_id in assertions
        and parse_time(assertions[successor_id].get("record_time")) is not None
        and when is not None
        and parse_time(assertions[successor_id].get("record_time")) <= when
        for successor_id in row.get("superseded_by") or []
    ):
        reasons.append("superseded")
    workflow = row.get("workflow_instance_id")
    if workflow and task.get("workflow_instance_id") and workflow != task.get("workflow_instance_id"):
        reasons.append("workflow_instance_mismatch")
    return sorted(set(reasons))


def conflict_winners(
    gold_row: dict,
    task: dict,
    assertions: dict[str, dict],
    activities: dict[str, dict],
    trust: dict[str, list[str]],
    semantics: dict[str, dict],
    mappings: list[dict],
    allowed_relations: set[str],
) -> list[str]:
    candidates_for_gold = normalized_candidates(gold_row, task, mappings)
    relation = next(iter(candidates_for_gold)) if len(candidates_for_gold) == 1 else canonical(gold_row.get("predicate"))
    rule = semantics.get(relation)
    if task.get("retrieval_mode") == "audit_historical" or not rule or rule.get("cardinality") == "multi_value":
        return [gold_row["assertion_id"]]
    owner = (
        gold_row.get("workflow_instance_id") or gold_row.get("subject")
        if rule.get("key") == "workflow_or_subject"
        else gold_row.get("subject")
    )
    candidates = []
    for row in assertions.values():
        normalized = normalized_candidates(row, task, mappings)
        if len(normalized) != 1 or next(iter(normalized)) != relation:
            continue
        row_owner = (
            row.get("workflow_instance_id") or row.get("subject")
            if rule.get("key") == "workflow_or_subject"
            else row.get("subject")
        )
        if row_owner != owner or base_reasons(row, task, assertions, activities, trust, mappings, allowed_relations):
            continue
        candidates.append(row)
    if not candidates or len({json.dumps(row.get("object"), sort_keys=True) for row in candidates}) < 2:
        return [row["assertion_id"] for row in candidates]
    tiers = trust.get(relation, [])
    best_rank = min(tiers.index(row.get("source")) for row in candidates)
    trusted = [row for row in candidates if tiers.index(row.get("source")) == best_rank]
    newest = max(parse_time(row.get("record_time")) for row in trusted)
    finalists = [row for row in trusted if parse_time(row.get("record_time")) == newest]
    if len({json.dumps(row.get("object"), sort_keys=True) for row in finalists}) > 1:
        return []
    winning_value = json.dumps(finalists[0].get("object"), sort_keys=True)
    return [
        row["assertion_id"]
        for row in finalists
        if json.dumps(row.get("object"), sort_keys=True) == winning_value
    ]


def contradicted_relations(
    task: dict,
    assertions: dict[str, dict],
    activities: dict[str, dict],
    trust: dict[str, list[str]],
    semantics: dict[str, dict],
    mappings: list[dict],
    allowed_relations: set[str],
) -> set[str]:
    """Relations for which the task's eligible pool holds incompatible values.

    Derived from the assertion store rather than from any recorded label, so a
    contradiction whose winner has been deleted from the label is still known to
    require an answer.
    """
    groups: dict[tuple, set[str]] = {}
    for row in assertions.values():
        normalized = normalized_candidates(row, task, mappings)
        if len(normalized) != 1:
            continue
        relation = next(iter(normalized))
        rule = semantics.get(relation)
        if not rule or rule.get("cardinality") == "multi_value":
            continue
        if base_reasons(row, task, assertions, activities, trust, mappings, allowed_relations):
            continue
        owner = (
            row.get("workflow_instance_id") or row.get("subject")
            if rule.get("key") == "workflow_or_subject"
            else row.get("subject")
        )
        groups.setdefault((owner, relation), set()).add(json.dumps(row.get("object"), sort_keys=True))
    return {relation for (_, relation), values in groups.items() if len(values) > 1}


def resolve_task_evidence(
    task: dict,
    assertions: dict[str, dict],
    activities: dict[str, dict],
    trust: dict[str, list[str]],
    semantics: dict[str, dict],
    mappings: list[dict],
    allowed_relations: set[str],
) -> tuple[list[dict], list[dict]]:
    """Independently derive all contract-permitted evidence for a task."""
    eligible = [
        row
        for row in assertions.values()
        if not base_reasons(row, task, assertions, activities, trust, mappings, allowed_relations)
    ]
    if task.get("retrieval_mode") == "audit_historical":
        return sorted(eligible, key=lambda row: row["assertion_id"]), []
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in eligible:
        normalized = normalized_candidates(row, task, mappings)
        if len(normalized) != 1:
            continue
        relation = next(iter(normalized))
        rule = semantics.get(relation)
        if not rule or rule.get("cardinality") == "multi_value":
            continue
        owner = row.get("workflow_instance_id") or row.get("subject") if rule.get("key") == "workflow_or_subject" else row.get("subject")
        grouped.setdefault((str(owner), relation), []).append(row)
    removed: set[str] = set()
    unresolved: list[dict] = []
    for (owner, relation), rows in sorted(grouped.items()):
        values = {json.dumps(row.get("object"), sort_keys=True) for row in rows}
        if len(values) < 2:
            continue
        tiers = trust.get(relation, [])
        best_rank = min(tiers.index(row.get("source")) for row in rows)
        trusted = [row for row in rows if tiers.index(row.get("source")) == best_rank]
        newest = max(parse_time(row.get("record_time")) for row in trusted)
        finalists = [row for row in trusted if parse_time(row.get("record_time")) == newest]
        finalist_values = {json.dumps(row.get("object"), sort_keys=True) for row in finalists}
        if len(finalist_values) > 1:
            removed.update(row["assertion_id"] for row in rows)
            unresolved.append({
                "key": [owner, relation],
                "predicate": relation,
                "assertion_ids": sorted(row["assertion_id"] for row in finalists),
            })
            continue
        winning_value = next(iter(finalist_values))
        winner_ids = {
            row["assertion_id"]
            for row in finalists
            if json.dumps(row.get("object"), sort_keys=True) == winning_value
        }
        removed.update(
            row["assertion_id"]
            for row in rows
            if row["assertion_id"] not in winner_ids
            and json.dumps(row.get("object"), sort_keys=True) != winning_value
        )
    return (
        sorted((row for row in eligible if row["assertion_id"] not in removed), key=lambda row: row["assertion_id"]),
        unresolved,
    )


def stage_label_errors(gold: dict) -> list[str]:
    """Check every released stage view instead of trusting one duplicated field."""
    errors: list[str] = []
    eligible = sorted(gold.get("eligible_assertion_ids") or [])
    equivalent = {
        "assertion_eligible_ids": gold.get("assertion_eligible_ids") or [],
        "resolved_eligible_assertion_ids": gold.get("resolved_eligible_assertion_ids") or [],
        "packet_eligible_assertion_ids": gold.get("packet_eligible_assertion_ids") or [],
        "stage_labels.AssertionEligible": (gold.get("stage_labels") or {}).get("AssertionEligible") or [],
        "stage_labels.B_q": (gold.get("stage_labels") or {}).get("B_q") or [],
        "stage_labels.PacketEligible": (gold.get("stage_labels") or {}).get("PacketEligible") or [],
    }
    for name, values in equivalent.items():
        if sorted(values) != eligible:
            errors.append(f"stage_mismatch:{name}")
    if sorted((gold.get("stage_labels") or {}).get("ActionAllowed") or []) != sorted(gold.get("valid_actions") or []):
        errors.append("stage_mismatch:ActionAllowed")
    stage_support = {
        key: sorted(value)
        for key, value in ((gold.get("stage_labels") or {}).get("ActionSupportEligible") or {}).items()
    }
    action_support = {key: sorted(value) for key, value in (gold.get("action_support_by_action") or {}).items()}
    if stage_support != action_support:
        errors.append("stage_mismatch:ActionSupportEligible")
    for name, values in equivalent.items():
        if len(values) != len(set(values)):
            errors.append(f"duplicate_ids:{name}")
    if len(eligible) != len(set(eligible)):
        errors.append("duplicate_ids:eligible_assertion_ids")
    for action, identifiers in action_support.items():
        if not set(identifiers) <= set(eligible):
            errors.append(f"support_not_eligible:{action}")
    return sorted(set(errors))


def main(data_root: Path | None = None) -> int:
    global DATA, GEN
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        data_root = parser.parse_args().data_root
    DATA = data_root.resolve()
    GEN = DATA / "generated"
    assertions = {row["assertion_id"]: row for row in read_jsonl(GEN / "assertion_events.jsonl")}
    activities = {row["activity_id"]: row for row in read_jsonl(GEN / "provenance_activities.jsonl")}
    trust = read_json(DATA / "config" / "trust_precedence.json")["relations"]
    semantics = read_json(DATA / "config" / "conflict_semantics.json")["relations"]
    mappings = read_json(DATA / "ontology" / "ontology_mappings.json").get("mappings", [])
    registry = {row["action"]: row for row in read_json(DATA / "config" / "action_registry.json").get("actions", [])}
    policies: dict[str, list[dict]] = {}
    for path in sorted((DATA / "policy").glob("*.json")):
        for rule in read_json(path).get("rules", []):
            policies.setdefault(rule.get("policy_version", path.stem), []).append(rule)
    workflows = {}
    for path in sorted((DATA / "workflows").glob("*.json")):
        document = read_json(path)
        workflows[document.get("workflow_type", path.stem)] = document
    failures, contract_failures, counts = [], [], {"permitted": 0, "retrospective": 0, "out_of_scope": 0}
    global_errors = []
    for assertion_id, row in assertions.items():
        for field in malformed_temporal_fields(row, ("event_time", "record_time", "valid_from", "valid_until")):
            global_errors.append(f"{assertion_id}:malformed_{field}")
        start, end = parse_time(row.get("valid_from")), parse_time(row.get("valid_until"))
        if start is not None and end is not None and not start < end:
            global_errors.append(f"{assertion_id}:invalid_validity_interval")
    task_reports = []
    for split in ("smoke", "dev", "test"):
        tasks = {row["task_id"]: row for row in read_jsonl(GEN / f"tasks_{split}.jsonl")}
        for gold in read_jsonl(GEN / f"gold_{split}.jsonl"):
            task = tasks[gold["task_id"]]
            for field in malformed_temporal_fields(task, ("decision_time", "audit_time")):
                global_errors.append(f"{task['task_id']}:malformed_{field}")
            allowed_relations = decision_relations(task, registry, policies, workflows)
            contract_reasons: list[str] = stage_label_errors(gold)
            task_reasons: list[str] = []
            resolved_rows, _ = resolve_task_evidence(
                task, assertions, activities, trust, semantics, mappings, allowed_relations
            )
            resolved_ids = {row["assertion_id"] for row in resolved_rows}
            for assertion_id in gold.get("eligible_assertion_ids") or []:
                row = assertions.get(assertion_id)
                if row is None:
                    task_reasons.append(f"{assertion_id}:absent")
                    contract_reasons.append(f"{assertion_id}:absent")
                    continue
                reasons = base_reasons(row, task, assertions, activities, trust, mappings, allowed_relations)
                task_reasons.extend(f"{assertion_id}:{reason}" for reason in reasons)
                if not reasons:
                    winners = conflict_winners(row, task, assertions, activities, trust, semantics, mappings, allowed_relations)
                    if assertion_id not in winners:
                        task_reasons.append(
                            f"{assertion_id}:conflict_loser:winners={','.join(sorted(winners)) or 'unresolved'}"
                        )
            if task.get("task_type") in EVIDENCE_ANSWER_TASK_TYPES:
                recorded = set(gold.get("eligible_assertion_ids") or [])
                if not recorded:
                    contract_reasons.append("required_answer_evidence_missing")
                # A required answer is one this task type must exhibit for a
                # relation. Deriving it from the independently resolved rows,
                # rather than only from the recorded label, means an emptied or
                # deleted label is reported as a contract failure instead of
                # silently satisfying the check and shifting the task's regime.
                required_relations = {canonical(value) for value in task.get("relation_scope") or []}
                if task.get("task_type") == "contradiction_handling":
                    required_relations &= contradicted_relations(
                        task, assertions, activities, trust, semantics, mappings, allowed_relations
                    )
                elif task.get("task_type") not in ALL_RELATIONS_REQUIRED_TASK_TYPES:
                    required_relations = set()
                for relation in sorted(required_relations):
                    if not any(
                        len(normalized_candidates(assertions[assertion_id], task, mappings)) == 1
                        and relation in normalized_candidates(assertions[assertion_id], task, mappings)
                        for assertion_id in recorded
                        if assertion_id in assertions
                    ):
                        contract_reasons.append(f"required_answer_relation_missing:{relation}")
                extra = sorted(recorded - resolved_ids)
                if extra:
                    task_reasons.append(f"answer_evidence_not_permitted:{','.join(extra)}")
            if contract_reasons:
                contract_failures.append({
                    "split": split,
                    "task_id": task["task_id"],
                    "reasons": sorted(set(contract_reasons)),
                })
            if any("recorded_after_query" in reason for reason in task_reasons):
                regime = "retrospective"
            elif any("_out_of_scope" in reason for reason in task_reasons):
                regime = "out_of_scope"
            else:
                regime = "permitted"
                if task_reasons:
                    failures.append({"split": split, "task_id": task["task_id"], "reasons": sorted(set(task_reasons))})
            task_reports.append({"split": split, "task_id": task["task_id"], "regime": regime, "reasons": sorted(set(task_reasons))})
            if split == "test":
                counts[regime] += 1
    report = {
        "checker": "validation-only-evidence-contract-verifier-v2",
        "writes_to_benchmark": False,
        "imports_evaluated_operator": False,
        "imports_label_generator": False,
        "test_task_regimes": counts,
        "global_errors": sorted(set(global_errors)),
        "label_contract_failures": contract_failures,
        "permitted_label_failures": failures,
        "all_task_reports": task_reports,
        "input_sha256": {
            "assertions": hashlib.sha256((GEN / "assertion_events.jsonl").read_bytes()).hexdigest(),
            "ontology_mappings": hashlib.sha256((DATA / "ontology" / "ontology_mappings.json").read_bytes()).hexdigest(),
        },
        "status": "pass" if not failures and not contract_failures and not global_errors else "fail",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures and not contract_failures and not global_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
