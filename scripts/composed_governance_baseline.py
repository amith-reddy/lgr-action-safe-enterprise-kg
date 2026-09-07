#!/usr/bin/env python3
"""Standalone deterministic composition of LGR's declared governance tables.

This comparator imports neither lgr_operator.py nor the label generators. It
implements conventional filter -> conflict resolution -> policy/workflow gate
composition and compares its result with saved LGR packets and frozen labels.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "evomem_enterprise"
ALIASES = {"support_plan": "support_entitlement", "entitlement_profile": "support_entitlement", "owner": "account_owner", "refund_status": "workflow_state"}
POLICY_TYPES = {"policy_fact", "action_permission", "workflow_policy_binding"}
WORKFLOW_TYPES = {"workflow_fact", "workflow_state", "workflow_event"}


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def canonical(value):
    return ALIASES.get(value, value)


def instant(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def targets(row, task, mappings):
    source, target, predicate = row.get("ontology_version"), task.get("target_ontology_version"), row.get("predicate")
    frontier, seen, result = {(source, predicate)}, set(), set()
    while frontier:
        version, relation = frontier.pop()
        if (version, relation) in seen:
            continue
        seen.add((version, relation))
        if version == target:
            result.add(canonical(relation))
        for item in mappings:
            if item.get("from_ov") == version and item.get("from_relation") == relation:
                frontier.add((item.get("to_ov"), item.get("to_relation")))
    if source == target:
        result.add(canonical(predicate))
    return {value for value in result if value}


def guard_relations(expression):
    if not expression:
        return set()
    if "and" in expression:
        return set().union(*(guard_relations(item) for item in expression["and"]))
    for operation in ("equals", "not_equals", "in"):
        if operation in expression:
            return {canonical(expression[operation][0])}
    return {canonical(expression["exists"])} if "exists" in expression else set()


def decision_relations(task, registry, policies, workflows):
    result = {canonical(value) for value in task.get("relation_scope") or []}
    for action in task.get("candidate_actions") or []:
        registration = registry.get(action)
        if not registration:
            continue
        for rule in policies.get(task.get("target_policy_version"), []):
            if rule.get("action") == action and rule.get("policy_family") == registration.get("policy_family"):
                result |= guard_relations(rule.get("guard"))
        workflow = workflows.get(registration.get("workflow_type"))
        if workflow:
            result.add("workflow_state")
            for transition in workflow.get("transitions", []):
                if transition.get("action") == action:
                    result |= guard_relations(transition.get("guard"))
    return result


def compose_evidence(task, assertions, activities, trust, mappings, semantics, registry, policies, workflows):
    when = instant(task.get("audit_time") if task.get("retrieval_mode") == "audit_historical" else task.get("decision_time"))
    allowed = decision_relations(task, registry, policies, workflows)
    index = {row["assertion_id"]: row for row in assertions}
    eligible = []
    for row in assertions:
        normalized = targets(row, task, mappings)
        if len(normalized) != 1 or next(iter(normalized)) not in allowed:
            continue
        relation = next(iter(normalized))
        query_entities = set(task.get("entity_scope") or [])
        entity_ok = row.get("subject") in query_entities or bool(query_entities & set(row.get("entity_scope") or [])) or bool(task.get("workflow_instance_id") and row.get("workflow_instance_id") == task.get("workflow_instance_id"))
        recorded, start, end = instant(row.get("record_time")), instant(row.get("valid_from")), instant(row.get("valid_until"))
        mode = task.get("retrieval_mode", "current_action")
        workflow_ok = not row.get("workflow_instance_id") or not task.get("workflow_instance_id") or row.get("workflow_instance_id") == task.get("workflow_instance_id")
        life_ok = row.get("lifecycle_state") == "active" if mode == "current_action" else row.get("lifecycle_state") not in {"deleted", "retracted"}
        policy_ok = row.get("assertion_type") not in POLICY_TYPES or row.get("policy_version") == task.get("target_policy_version")
        activity_ok = bool(row.get("provenance_activity") and activities.get(row.get("provenance_activity")) == row.get("source"))
        source_ok = row.get("source") in trust.get(relation, []) and row.get("source") not in set(task.get("disallowed_sources") or [])
        successor_visible = mode == "current_action" and any(sid in index and instant(index[sid].get("record_time")) and instant(index[sid].get("record_time")) <= when for sid in row.get("superseded_by") or [])
        if entity_ok and workflow_ok and when and recorded and recorded <= when and (not start or start <= when) and (not end or when < end) and life_ok and policy_ok and activity_ok and source_ok and not successor_visible:
            copy = dict(row)
            copy["_normalized_relation"] = relation
            eligible.append(copy)
    if task.get("retrieval_mode") == "audit_historical":
        return eligible, []
    groups = {}
    for row in eligible:
        relation = row["_normalized_relation"]
        rule = semantics.get(relation, {})
        if rule.get("cardinality") == "multi_value":
            continue
        owner = row.get("workflow_instance_id") or row.get("subject") if rule.get("key") == "workflow_or_subject" else row.get("subject")
        groups.setdefault((owner, relation), []).append(row)
    removed, unresolved = set(), []
    for key, rows in groups.items():
        if len({json.dumps(row.get("object"), sort_keys=True) for row in rows}) < 2:
            continue
        tiers = trust[key[1]]
        rank = min(tiers.index(row["source"]) for row in rows)
        top = [row for row in rows if tiers.index(row["source"]) == rank]
        newest = max(row.get("record_time") or "" for row in top)
        finalists = [row for row in top if (row.get("record_time") or "") == newest]
        values = {json.dumps(row.get("object"), sort_keys=True) for row in finalists}
        if len(values) > 1:
            removed |= {row["assertion_id"] for row in rows}
            unresolved.append({"key": key, "assertion_ids": sorted(row["assertion_id"] for row in finalists)})
        else:
            winning = next(iter(values))
            removed |= {row["assertion_id"] for row in rows if json.dumps(row.get("object"), sort_keys=True) != winning}
    return [row for row in eligible if row["assertion_id"] not in removed], unresolved


def guard(expression, facts, task):
    if not expression:
        return True, []
    if "and" in expression:
        evidence = []
        for child in expression["and"]:
            ok, ids = guard(child, facts, task)
            if not ok:
                return False, []
            evidence += ids
        return True, sorted(set(evidence))
    for operation in ("equals", "not_equals", "in"):
        if operation in expression:
            relation, expected = expression[operation]
            if relation not in facts:
                return False, []
            value, aid = facts[relation]
            ok = value == expected if operation == "equals" else value != expected if operation == "not_equals" else value in expected
            return ok, [aid]
    if "exists" in expression:
        relation = expression["exists"]
        return relation in facts, [facts[relation][1]] if relation in facts else []
    if "lte_hours_open" in expression:
        value = task.get("hours_open")
        return value is not None and float(value) <= float(expression["lte_hours_open"]), []
    return False, []


def action_binding(task, evidence, trust=None):
    """Resolve one action target from declarations, never from identifier shape.

    Only sources the trust table lists for ``workflow_state`` may declare which
    entities belong to a workflow case; membership is itself a governance
    statement. Without that restriction an untrusted record carrying the case
    identifier can enrol an unrelated entity and widen the action target.
    """
    declared = task.get("action_target")
    workflow_id = task.get("workflow_instance_id")
    scope = set(task.get("entity_scope") or [])
    membership_sources = set((trust or {}).get("workflow_state") or []) if trust is not None else None
    if declared:
        return {"subject": declared, "workflow_instance_id": workflow_id, "ambiguous": False}
    if workflow_id:
        declared_members = set()
        for row in evidence:
            if row.get("workflow_instance_id") != workflow_id or row.get("assertion_type") not in WORKFLOW_TYPES:
                continue
            if membership_sources is not None and row.get("source") not in membership_sources:
                continue
            if row.get("subject"):
                declared_members.add(row["subject"])
            declared_members.update(row.get("entity_scope") or [])
        related = declared_members & scope if scope else declared_members
        if related:
            return {
                "subject": None,
                "workflow_instance_id": workflow_id,
                "members": sorted(related | {workflow_id}),
                "ambiguous": False,
            }
    if len(scope) == 1:
        return {"subject": next(iter(scope)), "workflow_instance_id": workflow_id, "ambiguous": False}
    if workflow_id and not scope:
        return {"subject": None, "workflow_instance_id": workflow_id, "members": [workflow_id], "ambiguous": False}
    return {
        "subject": None,
        "workflow_instance_id": workflow_id,
        "members": sorted(scope),
        "ambiguous": len(scope) > 1,
    }


def binds(row, binding):
    if row.get("assertion_type") in POLICY_TYPES:
        return True
    workflow_id = binding.get("workflow_instance_id")
    row_workflow = row.get("workflow_instance_id")
    if row_workflow and workflow_id and row_workflow != workflow_id:
        return False
    members = set(binding.get("members") or [])
    if binding.get("subject"):
        members.add(binding["subject"])
    if not members:
        return True
    if row.get("subject") in members or members & set(row.get("entity_scope") or []):
        return True
    return bool(row_workflow and workflow_id and row_workflow == workflow_id)


def compose_actions(task, evidence, unresolved, registry, policies, workflows, trust=None):
    binding = action_binding(task, evidence, trust)
    chosen = {}
    for row in evidence:
        if not binds(row, binding):
            continue
        relation = row["_normalized_relation"]
        stamp = (row.get("record_time") or "", row["assertion_id"])
        if relation not in chosen or stamp > chosen[relation][0]:
            chosen[relation] = (stamp, row.get("object"), row["assertion_id"])
    facts = {relation: (value, aid) for relation, (_, value, aid) in chosen.items()}
    valid, blocked, support, reasons = [], [], {}, {}
    for action in task.get("candidate_actions") or []:
        failures, witnesses = [], []
        registration = registry.get(action)
        if not registration:
            blocked.append(action); reasons[action] = ["unregistered_action"]; continue
        if task.get("retrieval_mode") != "current_action" and registration.get("kind") == "effectful":
            blocked.append(action); reasons[action] = ["non_current_query"]; continue
        if registration.get("kind") == "effectful" and binding.get("ambiguous"):
            failures.append("ambiguous_action_binding")
        if registration.get("kind") == "advisory":
            critical = {canonical(value) for value in registration.get("critical_relations") or []}
            if any(canonical(item.get("key", [None, None])[-1]) in critical for item in unresolved):
                blocked.append(action); reasons[action] = ["critical_unresolved_conflict"]
            else:
                valid.append(action); support[action] = []
            continue
        rules = [r for r in policies.get(task.get("target_policy_version"), []) if r.get("action") == action and r.get("policy_family") == registration.get("policy_family")]
        satisfied = [(r, ids) for r in rules for ok, ids in [guard(r.get("guard"), facts, task)] if ok]
        if not rules:
            failures.append("missing_policy_binding")
        elif not satisfied:
            failures.append("policy_guard_failed")
        else:
            priority = max(r.get("priority", 0) for r, _ in satisfied)
            top = [(r, ids) for r, ids in satisfied if r.get("priority", 0) == priority]
            if any(r.get("permit_or_deny") == "deny" for r, _ in top):
                failures.append("policy_deny")
            else:
                witnesses += top[0][1]
        workflow = workflows.get(registration.get("workflow_type"))
        state = facts.get("workflow_state", (None, ""))[0]
        passing = [] if not workflow else [(tr, ids) for tr in workflow.get("transitions", []) if tr.get("action") == action and tr.get("from") == state for ok, ids in [guard(tr.get("guard"), facts, task)] if ok]
        if not workflow:
            failures.append("missing_workflow_binding")
        elif state is None:
            failures.append("missing_workflow_state_witness")
        elif not passing:
            failures.append("workflow_guard_failed")
        else:
            witnesses += passing[0][1] + [facts["workflow_state"][1]]
        critical = set()
        for rule in rules:
            critical |= guard_relations(rule.get("guard"))
        for transition in ([] if not workflow else workflow.get("transitions", [])):
            if transition.get("action") == action:
                critical |= guard_relations(transition.get("guard"))
        if any(canonical(item.get("key", [None, None])[-1]) in critical for item in unresolved):
            failures.append("critical_unresolved_conflict")
        if failures:
            blocked.append(action); reasons[action] = sorted(set(failures))
        else:
            valid.append(action); support[action] = sorted(set(witnesses))
    return {"valid_actions": valid, "blocked_actions": blocked, "support": support, "reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = args.data_root.resolve(); generated = data / "generated"
    assertions = read_jsonl(generated / "assertion_events.jsonl")
    activities = {row["activity_id"]: row["source"] for row in read_jsonl(generated / "provenance_activities.jsonl")}
    trust = read_json(data / "config" / "trust_precedence.json")["relations"]
    mappings = read_json(data / "ontology" / "ontology_mappings.json").get("mappings", [])
    semantics = read_json(data / "config" / "conflict_semantics.json")["relations"]
    registry = {row["action"]: row for row in read_json(data / "config" / "action_registry.json")["actions"]}
    policies = {}
    for path in (data / "policy").glob("*.json"):
        for rule in read_json(path).get("rules", []): policies.setdefault(rule.get("policy_version", path.stem), []).append(rule)
    workflows = {}
    for path in (data / "workflows").glob("*.json"):
        document = read_json(path); workflows[document.get("workflow_type", path.stem)] = document
    packets_path = data / "phase3" / "context_packets_test.jsonl"
    lgr_packets = {p["task_id"]: p for p in read_jsonl(packets_path) if p["method"] == "lifecycle_governed_kg_retrieval"} if packets_path.exists() else {}
    gold = {g["task_id"]: g for g in read_jsonl(generated / "gold_test.jsonl")}
    rows = []
    for task in read_jsonl(generated / "tasks_test.jsonl"):
        evidence, unresolved = compose_evidence(task, assertions, activities, trust, mappings, semantics, registry, policies, workflows)
        actions = compose_actions(task, evidence, unresolved, registry, policies, workflows, trust)
        packet = lgr_packets.get(task["task_id"], {})
        expected = gold[task["task_id"]]
        rows.append({
            "task_id": task["task_id"],
            "composed_evidence": sorted(row["assertion_id"] for row in evidence),
            "lgr_evidence": sorted(packet.get("retrieved_assertion_ids", [])),
            "evidence_equal_to_lgr": sorted(row["assertion_id"] for row in evidence) == sorted(packet.get("retrieved_assertion_ids", [])),
            "composed_valid_actions": sorted(actions["valid_actions"]),
            "gold_valid_actions": sorted(expected.get("valid_actions") or []),
            "composed_blocked_actions": sorted(actions["blocked_actions"]),
            "gold_blocked_actions": sorted(expected.get("blocked_actions") or []),
            "composed_support": {key: sorted(value) for key, value in actions["support"].items()},
            "gold_support": {key: sorted(value) for key, value in (expected.get("action_support_by_action") or {}).items()},
            "action_equal_to_gold": (
                sorted(actions["valid_actions"]) == sorted(expected.get("valid_actions") or [])
                and sorted(actions["blocked_actions"]) == sorted(expected.get("blocked_actions") or [])
                and {key: sorted(value) for key, value in actions["support"].items()}
                == {key: sorted(value) for key, value in (expected.get("action_support_by_action") or {}).items()}
            ),
        })
    action_rows = [row for row in rows if gold[row["task_id"]].get("valid_actions") or gold[row["task_id"]].get("blocked_actions")]
    report = {
        "comparator": "standalone-custom-governance-composition-v2",
        "imports_lgr_operator": False,
        "test_tasks": len(rows),
        "evidence_equal_to_lgr": sum(row["evidence_equal_to_lgr"] for row in rows),
        "action_tasks": len(action_rows),
        "action_equal_to_gold": sum(row["action_equal_to_gold"] for row in action_rows),
        "per_task": rows,
    }
    output = args.output or data / "phase3" / "composed_governance_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "per_task"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
