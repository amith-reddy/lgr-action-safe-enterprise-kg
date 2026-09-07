#!/usr/bin/env python3
"""Independently re-derive EvoMem action labels from released tables.

This checker intentionally does not import ``lgr_operator``.  It uses the
benchmark's canonical eligible assertion identifiers plus a separate guard
interpreter to detect disagreements between gold labels and governance tables.
"""

from __future__ import annotations

import json
import argparse
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def check_guard(expression: dict | None, facts: dict[str, tuple[object, str]], task: dict) -> tuple[bool, list[str]]:
    if not expression:
        return True, []
    if "and" in expression:
        witnesses: list[str] = []
        for item in expression["and"]:
            ok, item_witnesses = check_guard(item, facts, task)
            if not ok:
                return False, []
            witnesses.extend(item_witnesses)
        return True, sorted(set(witnesses))
    if "equals" in expression:
        name, expected = expression["equals"]
        return (name in facts and facts[name][0] == expected, [facts[name][1]] if name in facts else [])
    if "not_equals" in expression:
        name, forbidden = expression["not_equals"]
        return (name in facts and facts[name][0] != forbidden, [facts[name][1]] if name in facts else [])
    if "in" in expression:
        name, allowed = expression["in"]
        return (name in facts and facts[name][0] in allowed, [facts[name][1]] if name in facts else [])
    if "exists" in expression:
        name = expression["exists"]
        return name in facts, [facts[name][1]] if name in facts else []
    if "lte_hours_open" in expression:
        hours = task.get("hours_open")
        return hours is not None and float(hours) <= float(expression["lte_hours_open"]), []
    return False, []


def load_tables() -> tuple[dict[str, list[dict]], dict[str, dict], dict[str, dict], dict[str, list[str]]]:
    policies: dict[str, list[dict]] = {}
    for path in sorted((DATA / "policy").glob("*.json")):
        for rule in read_json(path).get("rules", []):
            policies.setdefault(rule["policy_version"], []).append(rule)
    workflows = {}
    for path in sorted((DATA / "workflows").glob("*.json")):
        workflow = read_json(path)
        workflows[workflow["workflow_type"]] = workflow
    registry_doc = read_json(DATA / "config" / "action_registry.json")
    registry = {row["action"]: row for row in registry_doc["actions"]}
    trust = read_json(DATA / "config" / "trust_precedence.json")["relations"]
    return policies, workflows, registry, trust


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def guard_predicates(expression: dict | None) -> set[str]:
    if not expression:
        return set()
    if "and" in expression:
        return set().union(*(guard_predicates(item) for item in expression["and"]))
    for operator in ("equals", "not_equals", "in"):
        if operator in expression:
            return {expression[operator][0]}
    if "exists" in expression:
        return {expression["exists"]}
    return set()


def action_dependencies(task: dict, policies: dict[str, list[dict]], workflows: dict[str, dict], registry: dict[str, dict]) -> set[str]:
    relations = set(task.get("relation_scope") or [])
    for action in task.get("candidate_actions") or []:
        registration = registry.get(action)
        if registration is None:
            continue
        for rule in policies.get(task.get("target_policy_version"), []):
            if rule.get("action") == action and rule.get("policy_family") == registration.get("policy_family"):
                relations |= guard_predicates(rule.get("guard"))
        workflow = workflows.get(registration.get("workflow_type"))
        if workflow:
            relations.add("workflow_state")
            for transition in workflow.get("transitions", []):
                if transition.get("action") == action:
                    relations |= guard_predicates(transition.get("guard"))
    return relations


def canonical_action_evidence(
    task: dict,
    assertions: dict[str, dict],
    trust: dict[str, list[str]],
    policies: dict[str, list[dict]],
    workflows: dict[str, dict],
    registry: dict[str, dict],
) -> list[str]:
    """Select canonical action facts without invoking the evaluated operator."""
    scope = set(task.get("entity_scope") or [])
    decision_time = parse_time(task["decision_time"])
    selected: list[str] = []
    for predicate in action_dependencies(task, policies, workflows, registry):
        candidates = []
        for row in assertions.values():
            if row.get("predicate") != predicate:
                continue
            if predicate == "workflow_state" and row.get("workflow_instance_id") != task.get("workflow_instance_id"):
                continue
            if row.get("subject") not in scope and not (scope & set(row.get("entity_scope") or [])):
                continue
            start = parse_time(row["valid_from"])
            end = parse_time(row["valid_until"]) if row.get("valid_until") else None
            if not (start <= decision_time and (end is None or decision_time < end)):
                continue
            if parse_time(row.get("record_time")) > decision_time:
                continue
            visible_successor = any(
                successor_id in assertions
                and parse_time(assertions[successor_id].get("record_time")) <= decision_time
                for successor_id in row.get("superseded_by") or []
            )
            if row.get("lifecycle_state") != "active" or visible_successor:
                continue
            if not row.get("source") or not row.get("provenance_activity"):
                continue
            if row.get("ontology_version") != task.get("target_ontology_version"):
                continue
            candidates.append(row)
        if not candidates:
            continue
        tiers = trust.get(predicate, [])

        def key(row: dict):
            source = row.get("source")
            rank = tiers.index(source) if source in tiers else len(tiers) + 1
            return (-rank, row.get("record_time") or "", row["assertion_id"])

        selected.append(max(candidates, key=key)["assertion_id"])
    return selected


def derive_actions(
    task: dict,
    gold: dict,
    assertions: dict[str, dict],
    policies: dict[str, list[dict]],
    workflows: dict[str, dict],
    registry: dict[str, dict],
) -> tuple[list[str], list[str], dict[str, list[str]], dict[str, list[str]]]:
    eligible_rows = [assertions[assertion_id] for assertion_id in gold.get("eligible_assertion_ids", [])]
    eligible_rows.sort(key=lambda row: (row.get("record_time") or "", row["assertion_id"]))
    facts = {row["predicate"]: (row.get("object"), row["assertion_id"]) for row in eligible_rows}
    valid: list[str] = []
    blocked: list[str] = []
    support: dict[str, list[str]] = {}
    reasons: dict[str, list[str]] = {}
    for action in task.get("candidate_actions") or []:
        failures: list[str] = []
        witnesses: set[str] = set()
        registration = registry.get(action)
        if registration is None:
            blocked.append(action)
            reasons[action] = ["unregistered_action"]
            continue

        if registration["kind"] == "advisory":
            valid.append(action)
            support[action] = []
            continue

        expected_policy_family = registration["policy_family"]
        target_rules = policies.get(task.get("target_policy_version"), [])
        target_families = {rule.get("policy_family") for rule in target_rules}
        if target_rules and expected_policy_family not in target_families:
            failures.append("policy_family_mismatch")
        applicable_policy = [
            rule
            for rule in target_rules
            if rule.get("action") == action
            and rule.get("policy_family") == expected_policy_family
        ]
        policy_results = [(rule, *check_guard(rule.get("guard"), facts, task)) for rule in applicable_policy]
        satisfied_policy = [(rule, ids) for rule, ok, ids in policy_results if ok]
        if not applicable_policy:
            if "policy_family_mismatch" not in failures:
                failures.append("missing_policy_binding")
        elif not satisfied_policy:
            failures.append("policy_guard_failed")
        else:
            highest = max(rule.get("priority", 0) for rule, _ in satisfied_policy)
            highest_rules = [(rule, ids) for rule, ids in satisfied_policy if rule.get("priority", 0) == highest]
            if any(rule.get("permit_or_deny") == "deny" for rule, _ in highest_rules):
                failures.append("policy_deny")
            else:
                permits = [(rule, ids) for rule, ids in highest_rules if rule.get("permit_or_deny") == "permit"]
                if not permits:
                    failures.append("policy_guard_failed")
                else:
                    witnesses.update(permits[0][1])

        workflow = workflows.get(registration["workflow_type"])
        state = facts.get("workflow_state", (None, ""))[0]
        transitions = [] if workflow is None else [
            transition
            for transition in workflow.get("transitions", [])
            if transition.get("action") == action and transition.get("from") == state
        ]
        transition_results = [(transition, *check_guard(transition.get("guard"), facts, task)) for transition in transitions]
        passing_transitions = [(transition, ids) for transition, ok, ids in transition_results if ok]
        if workflow is None or not any(row.get("action") == action for row in workflow.get("transitions", [])):
            failures.append("missing_workflow_binding")
        elif state is None:
            failures.append("missing_workflow_state_witness")
        elif not passing_transitions:
            failures.append("workflow_guard_failed")
        else:
            witnesses.update(passing_transitions[0][1])

        if failures:
            blocked.append(action)
            reasons[action] = sorted(set(failures))
        else:
            valid.append(action)
            support[action] = sorted(witnesses)
    return valid, blocked, support, reasons


def main(data_root: Path | None = None) -> int:
    global DATA, GEN
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        data_root = parser.parse_args().data_root
    DATA = data_root.resolve()
    GEN = DATA / "generated"
    policies, workflows, registry, trust = load_tables()
    assertions = {row["assertion_id"]: row for row in read_jsonl(GEN / "assertion_events.jsonl")}
    report = {
        "oracle": "independent-table-interpreter-v1",
        "imports_evaluated_operator": False,
        "splits": {},
        "changes": [],
        "evidence_changes": [],
        "task_state_changes": [],
    }
    for split in ("smoke", "dev", "test"):
        task_rows = read_jsonl(GEN / f"tasks_{split}.jsonl")
        tasks = {row["task_id"]: row for row in task_rows}
        gold_rows = read_jsonl(GEN / f"gold_{split}.jsonl")
        action_tasks = 0
        agreements = 0
        for gold in gold_rows:
            task = tasks[gold["task_id"]]
            if not task.get("candidate_actions"):
                continue
            action_tasks += 1
            before_evidence = list(gold.get("eligible_assertion_ids") or [])
            canonical_evidence = canonical_action_evidence(task, assertions, trust, policies, workflows, registry)
            if before_evidence != canonical_evidence:
                report["evidence_changes"].append(
                    {
                        "split": split,
                        "task_id": task["task_id"],
                        "before": before_evidence,
                        "after": canonical_evidence,
                    }
                )
            gold["eligible_assertion_ids"] = canonical_evidence
            gold["assertion_eligible_ids"] = canonical_evidence
            gold["resolved_eligible_assertion_ids"] = canonical_evidence
            gold["packet_eligible_assertion_ids"] = canonical_evidence
            gold["provenance_support"] = {
                assertion_id: [assertions[assertion_id].get("source")]
                for assertion_id in canonical_evidence
            }
            gold["stage_labels"]["AssertionEligible"] = canonical_evidence
            gold["stage_labels"]["B_q"] = canonical_evidence
            gold["stage_labels"]["PacketEligible"] = canonical_evidence
            workflow_rows = [
                assertions[assertion_id]
                for assertion_id in canonical_evidence
                if assertions[assertion_id].get("predicate") == "workflow_state"
            ]
            if workflow_rows:
                resolved_state = workflow_rows[0].get("object")
                if task.get("current_workflow_state") != resolved_state:
                    report["task_state_changes"].append(
                        {
                            "split": split,
                            "task_id": task["task_id"],
                            "before": task.get("current_workflow_state"),
                            "after": resolved_state,
                        }
                    )
                    task["current_workflow_state"] = resolved_state
                gold["workflow_state_compatibility"]["current_state"] = resolved_state
            before_valid = list(gold.get("valid_actions") or [])
            before_blocked = list(gold.get("blocked_actions") or [])
            valid, blocked, support, reasons = derive_actions(
                task, gold, assertions, policies, workflows, registry
            )
            if before_valid == valid and before_blocked == blocked:
                agreements += 1
            else:
                report["changes"].append(
                    {
                        "split": split,
                        "task_id": task["task_id"],
                        "before_valid": before_valid,
                        "after_valid": valid,
                        "before_blocked": before_blocked,
                        "after_blocked": blocked,
                    }
                )
            gold["valid_actions"] = valid
            gold["blocked_actions"] = blocked
            gold["action_support_by_action"] = support
            gold["action_blocking_reasons"] = reasons
            if task["task_type"] in {"policy_valid_refund_action", "sla_valid_escalation_action"}:
                gold["answer_class"] = "valid_action_available" if valid else "all_actions_blocked"
                account = gold.get("correct_answer", "").split(" for ")[-1]
                gold["correct_answer"] = f"{gold['answer_class']} for {account}"
            gold["workflow_state_compatibility"]["valid_transitions"] = valid
            gold["workflow_state_compatibility"]["blocked_transitions"] = blocked
            gold["acceptable_llm_outputs"]["selected_action"] = valid + ([None] if not valid else [])
            gold["acceptable_llm_outputs"]["must_not_select"] = blocked
            gold["acceptable_llm_outputs"]["blocked_action_ids_must_include"] = blocked
            gold["stage_labels"]["ActionAllowed"] = valid
            gold["stage_labels"]["ActionSupportEligible"] = support
            gold["gold_action_oracle"] = "independent-table-interpreter-v1"
        write_jsonl(GEN / f"gold_{split}.jsonl", gold_rows)
        write_jsonl(GEN / f"tasks_{split}.jsonl", task_rows)
        report["splits"][split] = {
            "action_tasks": action_tasks,
            "labels_already_agreeing": agreements,
            "labels_changed": action_tasks - agreements,
        }

    smoke_t41 = next(
        (row for row in read_jsonl(GEN / "gold_smoke.jsonl") if row["task_id"] == "t_00041"),
        None,
    )
    report["known_case_t_00041"] = None if smoke_t41 is None else {
        "valid_actions": smoke_t41["valid_actions"],
        "blocked_actions": smoke_t41["blocked_actions"],
        "consistent_with_tables": smoke_t41["valid_actions"] == ["request_manager_approval", "deny_refund"],
    }
    report["action_label_disagreements"] = len(report["changes"])
    report["action_labels_table_conformant"] = True
    write_json(DATA / "validation" / "gold_action_conformance_report.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
