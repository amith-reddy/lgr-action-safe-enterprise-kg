#!/usr/bin/env python3
"""Validation-only check of the frozen action labels.

`rederive_evomem_gold.py` *generates* labels: it recomputes evidence and action
sets and writes them back into the gold files.  A generator cannot witness its
own output, so this script is deliberately separate and does the opposite job:

  * it never writes to the benchmark;
  * it re-derives each frozen action label from the versioned governance tables
    with its own interpreter, importing neither the evaluated LGR operator nor
    the label generator; and
  * it exits non-zero on any disagreement, so a drifted label fails a run
    instead of being silently rewritten.

It verifies labels against the tables.  It cannot establish that the tables
encode an organization's real policy.
"""

from __future__ import annotations

import json
import sys
import argparse
import hashlib
from pathlib import Path

import verify_evidence_labels as evidence_semantics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"

POLICY_TYPES = {"policy_fact", "action_permission", "workflow_policy_binding"}
WORKFLOW_TYPES = {"workflow_fact", "workflow_state", "workflow_event"}
CANONICAL = {
    "support_plan": "support_entitlement",
    "entitlement_profile": "support_entitlement",
    "support_entitlement": "support_entitlement",
    "owner": "account_owner",
    "account_owner": "account_owner",
    "refund_status": "workflow_state",
    "workflow_state": "workflow_state",
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(relation):
    return CANONICAL.get(relation, relation)


def load_tables():
    registry = {row["action"]: row for row in read_json(DATA / "config" / "action_registry.json")["actions"]}
    policies = {p.stem: read_json(p).get("rules", []) for p in sorted((DATA / "policy").glob("*.json"))}
    workflows = {p.stem: read_json(p) for p in sorted((DATA / "workflows").glob("*.json"))}
    return registry, policies, workflows


def guard_holds(expression, facts, task) -> tuple[bool, list[str]]:
    if not expression:
        return True, []
    if "and" in expression:
        witnesses = []
        for child in expression["and"]:
            ok, child_witnesses = guard_holds(child, facts, task)
            if not ok:
                return False, []
            witnesses.extend(child_witnesses)
        return True, sorted(set(witnesses))
    if "equals" in expression:
        predicate, expected = expression["equals"]
        return (predicate in facts and facts[predicate][0] == expected, [facts[predicate][1]] if predicate in facts else [])
    if "not_equals" in expression:
        predicate, forbidden = expression["not_equals"]
        return (predicate in facts and facts[predicate][0] != forbidden, [facts[predicate][1]] if predicate in facts else [])
    if "in" in expression:
        predicate, allowed = expression["in"]
        return (predicate in facts and facts[predicate][0] in set(allowed), [facts[predicate][1]] if predicate in facts else [])
    if "exists" in expression:
        predicate = expression["exists"]
        return predicate in facts, [facts[predicate][1]] if predicate in facts else []
    if "lte_hours_open" in expression:
        value = task.get("hours_open")
        return value is not None and float(value) <= float(expression["lte_hours_open"]), []
    return False, []


def action_binding(task, evidence_rows, trust=None) -> dict:
    """Resolve the action target, honouring the source restriction on membership.

    Workflow membership is a governance statement, so only sources the trust
    table lists for ``workflow_state`` may declare who belongs to a case. Without
    this restriction a record from an unrelated source can enrol a third party
    into the case and widen the action target.
    """
    declared = task.get("action_target")
    workflow_id = task.get("workflow_instance_id")
    scope = set(task.get("entity_scope") or [])
    membership_sources = set((trust or {}).get("workflow_state") or []) if trust is not None else None
    if declared:
        return {"subject": declared, "workflow_instance_id": workflow_id, "ambiguous": False}
    if workflow_id:
        declared_members = set()
        for row in evidence_rows:
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
    return {"subject": None, "workflow_instance_id": workflow_id, "members": sorted(scope), "ambiguous": len(scope) > 1}


def binds(row, binding) -> bool:
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
    return (
        row.get("subject") in members
        or bool(members & set(row.get("entity_scope") or []))
        or bool(row_workflow and workflow_id and row_workflow == workflow_id)
    )


def facts_from(evidence_rows, binding) -> dict:
    """Latest value per canonical relation, restricted to the action's target."""
    chosen: dict[str, tuple[tuple[str, str], object, str]] = {}
    for row in evidence_rows:
        assertion_id = row.get("assertion_id")
        if not assertion_id or not binds(row, binding):
            continue
        relation = canonical(row.get("predicate"))
        if not relation:
            continue
        stamp = (row.get("record_time") or "", assertion_id)
        previous = chosen.get(relation)
        if previous is None or stamp > previous[0]:
            chosen[relation] = (stamp, row.get("object"), assertion_id)
    return {relation: (value, assertion_id) for relation, (_, value, assertion_id) in chosen.items()}


def expected_actions(task, evidence_rows, unresolved, registry, policies, workflows, trust=None):
    binding = action_binding(task, evidence_rows, trust)
    facts = facts_from(evidence_rows, binding)
    target_policy = task.get("target_policy_version")
    valid, blocked = [], []
    support: dict[str, list[str]] = {}
    reasons: dict[str, list[str]] = {}
    for action in task.get("candidate_actions") or []:
        registration = registry.get(action)
        if registration is None:
            blocked.append(action)
            reasons[action] = ["unregistered_action"]
            continue
        if task.get("retrieval_mode", "current_action") != "current_action" and registration["kind"] == "effectful":
            blocked.append(action)
            reasons[action] = ["non_current_query"]
            continue
        preconditions = []
        if registration["kind"] == "effectful" and binding.get("ambiguous"):
            preconditions.append("ambiguous_action_binding")
        if registration["kind"] == "advisory":
            critical = {canonical(value) for value in registration.get("critical_relations") or []}
            if any(canonical(item.get("predicate")) in critical for item in unresolved):
                blocked.append(action)
                reasons[action] = ["critical_unresolved_conflict"]
            else:
                valid.append(action)
                support[action] = []
            continue
        family = registration.get("policy_family")
        rules = [
            rule
            for rule in policies.get(target_policy, [])
            if rule.get("action") == action and rule.get("policy_family") == family
        ]
        evaluated_rules = [(rule, *guard_holds(rule.get("guard"), facts, task)) for rule in rules]
        satisfied = [(rule, witnesses) for rule, ok, witnesses in evaluated_rules if ok]
        permitted = False
        policy_witnesses: list[str] = []
        if satisfied:
            top = max(rule.get("priority", 0) for rule, _ in satisfied)
            top_rules = [(rule, witnesses) for rule, witnesses in satisfied if rule.get("priority", 0) == top]
            permitted = bool(top_rules) and all(rule.get("permit_or_deny") == "permit" for rule, _ in top_rules)
            if permitted:
                policy_witnesses = top_rules[0][1]
        workflow = workflows.get(registration.get("workflow_type"))
        state = facts.get("workflow_state", (None, ""))[0]
        enabled = False
        workflow_witnesses: list[str] = []
        if workflow is not None and state is not None:
            for transition in workflow.get("transitions", []):
                if transition.get("action") != action or transition.get("from") != state:
                    continue
                ok, witnesses = guard_holds(transition.get("guard"), facts, task)
                if ok:
                    enabled, workflow_witnesses = True, witnesses
                    break
        critical = set()
        for rule in rules:
            critical |= evidence_semantics.guard_relations(rule.get("guard"))
        if workflow is not None:
            for transition in workflow.get("transitions", []):
                if transition.get("action") == action:
                    critical |= evidence_semantics.guard_relations(transition.get("guard"))
        if any(canonical(item.get("predicate")) in critical for item in unresolved):
            preconditions.append("critical_unresolved_conflict")
        if permitted and enabled and not preconditions:
            valid.append(action)
            support[action] = sorted(set(policy_witnesses + workflow_witnesses + ([facts["workflow_state"][1]] if "workflow_state" in facts else [])))
        else:
            blocked.append(action)
            failures = list(preconditions)
            if not rules:
                failures.append("missing_policy_binding")
            elif not satisfied:
                failures.append("policy_guard_failed")
            elif not permitted:
                failures.append("policy_deny")
            if workflow is None:
                failures.append("missing_workflow_binding")
            elif state is None:
                failures.append("missing_workflow_state_witness")
            elif not enabled:
                failures.append("workflow_guard_failed")
            reasons[action] = sorted(set(failures))
    return valid, blocked, support, reasons


def main(data_root: Path | None = None) -> int:
    global DATA, GEN
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        data_root = parser.parse_args().data_root
    DATA = data_root.resolve()
    GEN = DATA / "generated"
    registry, policies, workflows = load_tables()
    assertions = {row["assertion_id"]: row for row in read_jsonl(GEN / "assertion_events.jsonl")}
    activities = {row["activity_id"]: row for row in read_jsonl(GEN / "provenance_activities.jsonl")}
    trust = read_json(DATA / "config" / "trust_precedence.json")["relations"]
    semantics = read_json(DATA / "config" / "conflict_semantics.json")["relations"]
    mappings = read_json(DATA / "ontology" / "ontology_mappings.json").get("mappings", [])
    disagreements = []
    checked = 0
    for split in ("smoke", "dev", "test"):
        tasks = {row["task_id"]: row for row in read_jsonl(GEN / f"tasks_{split}.jsonl")}
        for gold in read_jsonl(GEN / f"gold_{split}.jsonl"):
            task = tasks[gold["task_id"]]
            if not task.get("candidate_actions"):
                continue
            checked += 1
            allowed_relations = evidence_semantics.decision_relations(task, registry, policies, workflows)
            evidence_rows, unresolved = evidence_semantics.resolve_task_evidence(
                task, assertions, activities, trust, semantics, mappings, allowed_relations
            )
            valid, blocked, support, reasons = expected_actions(
                task, evidence_rows, unresolved, registry, policies, workflows, trust
            )
            recorded_valid = list(gold.get("valid_actions") or [])
            recorded_blocked = list(gold.get("blocked_actions") or [])
            recorded_support = {key: sorted(value) for key, value in (gold.get("action_support_by_action") or {}).items()}
            recorded_reasons = {key: sorted(value) for key, value in (gold.get("action_blocking_reasons") or {}).items()}
            if (
                sorted(valid) != sorted(recorded_valid)
                or sorted(blocked) != sorted(recorded_blocked)
                or support != recorded_support
                or reasons != recorded_reasons
            ):
                disagreements.append(
                    {
                        "split": split,
                        "task_id": task["task_id"],
                        "recorded_valid": sorted(recorded_valid),
                        "verified_valid": sorted(valid),
                        "recorded_blocked": sorted(recorded_blocked),
                        "verified_blocked": sorted(blocked),
                        "recorded_support": recorded_support,
                        "verified_support": support,
                        "recorded_reasons": recorded_reasons,
                        "verified_reasons": reasons,
                    }
                )
    report = {
        "checker": "validation-only-label-verifier-v3",
        "writes_to_benchmark": False,
        "imports_evaluated_operator": False,
        "imports_label_generator": False,
        "derives_decision_evidence_from_snapshot": True,
        "action_labels_checked": checked,
        "disagreements": disagreements,
        "input_sha256": {
            "assertions": hashlib.sha256((GEN / "assertion_events.jsonl").read_bytes()).hexdigest(),
            "gold_test": hashlib.sha256((GEN / "gold_test.jsonl").read_bytes()).hexdigest(),
        },
        "status": "pass" if not disagreements else "fail",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not disagreements else 1


if __name__ == "__main__":
    raise SystemExit(main())
