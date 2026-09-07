#!/usr/bin/env python3
"""Validate the EvoMem-Enterprise generated artifacts."""

from __future__ import annotations

import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "evomem_enterprise"
GEN = OUT / "generated"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main(data_root: Path | None = None) -> int:
    global OUT, GEN
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=OUT)
        data_root = parser.parse_args().data_root
    OUT = data_root.resolve()
    GEN = OUT / "generated"
    errors: list[str] = []
    required_files = [
        OUT / "config" / "benchmark_config.yaml",
        OUT / "config" / "seeds.yaml",
        OUT / "config" / "conflict_semantics.json",
        OUT / "schema" / "entities.schema.json",
        OUT / "schema" / "assertion_event.schema.json",
        OUT / "schema" / "task.schema.json",
        OUT / "schema" / "gold_label.schema.json",
        OUT / "schema" / "context_packet.schema.json",
        OUT / "schema" / "llm_output.schema.json",
        OUT / "ontology" / "ontology_v1.json",
        OUT / "ontology" / "ontology_v2.json",
        OUT / "ontology" / "ontology_v3.json",
        OUT / "ontology" / "ontology_mappings.json",
        OUT / "policy" / "refund_policy_v1.json",
        OUT / "policy" / "refund_policy_v2.json",
        OUT / "policy" / "sla_policy_v1.json",
        OUT / "policy" / "sla_policy_v2.json",
        OUT / "workflows" / "refund_workflow.json",
        OUT / "workflows" / "support_escalation_workflow.json",
        ROOT / "scripts" / "score_evomem_llm_outputs.py",
        GEN / "entities.jsonl",
        GEN / "canonical_state_timeline.jsonl",
        GEN / "state_changes.jsonl",
        GEN / "assertion_events.jsonl",
        GEN / "contradiction_groups.jsonl",
        GEN / "tasks_smoke.jsonl",
        GEN / "tasks_dev.jsonl",
        GEN / "tasks_test.jsonl",
        GEN / "gold_smoke.jsonl",
        GEN / "gold_dev.jsonl",
        GEN / "gold_test.jsonl",
        OUT / "prompts" / "llm_action_eval_prompt.txt",
    ]
    for path in required_files:
        if not path.exists():
            fail(errors, f"missing required artifact: {path}")

    if errors:
        report = {"status": "fail", "errors": errors}
        (OUT / "validation").mkdir(parents=True, exist_ok=True)
        (OUT / "validation" / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    entities = load_jsonl(GEN / "entities.jsonl")
    assertions = load_jsonl(GEN / "assertion_events.jsonl")
    changes = load_jsonl(GEN / "state_changes.jsonl")
    contradictions = load_jsonl(GEN / "contradiction_groups.jsonl")
    tasks = []
    gold = []
    for split in ["smoke", "dev", "test"]:
        tasks.extend(load_jsonl(GEN / f"tasks_{split}.jsonl"))
        gold.extend(load_jsonl(GEN / f"gold_{split}.jsonl"))

    assertion_ids = {a["assertion_id"] for a in assertions}
    task_ids = {t["task_id"] for t in tasks}
    gold_by_task = {g["task_id"]: g for g in gold}
    contradiction_ids = {c["contradiction_group_id"] for c in contradictions}

    if len(entities) < 100:
        fail(errors, f"entity count below minimum: {len(entities)}")
    if len(assertions) < 500:
        fail(errors, f"assertion count below minimum: {len(assertions)}")
    if len(changes) < 100:
        fail(errors, f"state-change count below minimum: {len(changes)}")
    if len(tasks) < 100:
        fail(errors, f"task count below minimum: {len(tasks)}")
    if len(contradictions) < 50:
        fail(errors, f"contradiction count below minimum: {len(contradictions)}")

    if len(assertion_ids) != len(assertions):
        fail(errors, "assertion ids are not unique")
    if len(task_ids) != len(tasks):
        fail(errors, "task ids are not unique")
    if task_ids != set(gold_by_task):
        fail(errors, "tasks and gold labels do not have one-to-one task ids")

    ontology_count = len(list((OUT / "ontology").glob("ontology_v*.json")))
    policy_files = list((OUT / "policy").glob("*.json"))
    workflow_files = list((OUT / "workflows").glob("*.json"))
    if ontology_count < 3:
        fail(errors, "fewer than three ontology versions")
    if len(policy_files) < 4:
        fail(errors, "fewer than four policy version artifacts")
    if len(workflow_files) < 2:
        fail(errors, "fewer than two workflow artifacts")

    conflict_doc = load_json(OUT / "config" / "conflict_semantics.json")
    conflict_relations = conflict_doc.get("relations", {})
    if not conflict_doc.get("version") or not isinstance(conflict_relations, dict):
        fail(errors, "invalid conflict semantics configuration")
    for relation in load_json(OUT / "config" / "trust_precedence.json").get("relations", {}):
        spec = conflict_relations.get(relation)
        if not isinstance(spec, dict):
            fail(errors, f"conflict semantics missing trust relation: {relation}")
        elif spec.get("cardinality") not in {"single_value", "multi_value"}:
            fail(errors, f"conflict semantics has invalid cardinality: {relation}")

    transitions_by_workflow = {}
    transition_actions_by_state = defaultdict(set)
    for path in workflow_files:
        wf = load_json(path)
        transitions_by_workflow[wf["workflow_type"]] = {(tr["from"], tr["action"]): tr for tr in wf["transitions"]}
        for tr in wf["transitions"]:
            transition_actions_by_state[tr["from"]].add(tr["action"])
            if "guard" not in tr:
                fail(errors, f"workflow transition missing guard: {path.name} {tr}")

    required_task_fields = {
        "task_id",
        "task_type",
        "decision_time",
        "entity_scope",
        "entity_scope_mode",
        "target_ontology_version",
        "target_policy_version",
        "retrieval_mode",
        "candidate_actions",
        "assertion_templates",
    }
    for t in tasks:
        missing = required_task_fields - set(t)
        if missing:
            fail(errors, f"task {t.get('task_id')} missing fields {sorted(missing)}")
        if t["task_type"] in {"policy_valid_refund_action", "workflow_state_next_action", "sla_valid_escalation_action"}:
            if not t.get("current_workflow_state") or not t.get("workflow_instance_id"):
                fail(errors, f"workflow task missing workflow fields: {t['task_id']}")

    for c in contradictions:
        ids = c.get("assertion_ids", [])
        if len(ids) < 2:
            fail(errors, f"contradiction group has fewer than two assertions: {c['contradiction_group_id']}")
        for aid in ids:
            if aid not in assertion_ids:
                fail(errors, f"contradiction references missing assertion {aid}")
        if not c.get("winner_assertion_id") and not c.get("unresolved"):
            fail(errors, f"contradiction group has no winner or unresolved flag: {c['contradiction_group_id']}")
        if c.get("winner_assertion_id") and c["winner_assertion_id"] not in ids:
            fail(errors, f"contradiction winner not in assertion list: {c['contradiction_group_id']}")

    required_gold_fields = {
        "task_id",
        "answer_class",
        "eligible_assertion_ids",
        "expected_suppression",
        "valid_actions",
        "blocked_actions",
        "acceptable_llm_outputs",
        "stage_labels",
    }
    for g in gold:
        task = next((t for t in tasks if t["task_id"] == g["task_id"]), None)
        missing = required_gold_fields - set(g)
        if missing:
            fail(errors, f"gold {g.get('task_id')} missing fields {sorted(missing)}")
        if not task:
            fail(errors, f"gold has no task record: {g.get('task_id')}")
            continue
        candidate_actions = set(task.get("candidate_actions", []))
        valid_actions = set(g.get("valid_actions", []))
        blocked_actions = set(g.get("blocked_actions", []))
        if not valid_actions.issubset(candidate_actions):
            fail(errors, f"gold {g['task_id']} valid actions not in task candidates: {sorted(valid_actions - candidate_actions)}")
        if not blocked_actions.issubset(candidate_actions):
            fail(errors, f"gold {g['task_id']} blocked actions not in task candidates: {sorted(blocked_actions - candidate_actions)}")
        state = task.get("current_workflow_state")
        if state:
            allowed = transition_actions_by_state.get(state, set())
            if not valid_actions.issubset(allowed):
                fail(errors, f"gold {g['task_id']} valid actions not allowed by workflow state {state}: {sorted(valid_actions - allowed)}")
        for field in ["eligible_assertion_ids", "stale_or_superseded_assertion_ids", "contradiction_winner_ids"]:
            for aid in g.get(field, []):
                if aid not in assertion_ids:
                    fail(errors, f"gold {g['task_id']} references missing assertion {aid} in {field}")
        for aid in g.get("expected_suppression", {}):
            if aid not in assertion_ids:
                fail(errors, f"gold {g['task_id']} suppresses missing assertion {aid}")
        for cg in g.get("contradiction_group_ids", []):
            if cg not in contradiction_ids:
                fail(errors, f"gold {g['task_id']} references missing contradiction {cg}")
        llm = g.get("acceptable_llm_outputs", {})
        if "required_support_sets" not in llm or "support_scoring_rule" not in llm:
            fail(errors, f"gold {g['task_id']} lacks deterministic LLM support scoring")
        stages = g.get("stage_labels", {})
        for s in ["AssertionEligible", "B_q", "ActionAllowed", "ActionSupportEligible", "PacketEligible"]:
            if s not in stages:
                fail(errors, f"gold {g['task_id']} missing stage label {s}")

    smoke_tasks = load_jsonl(GEN / "tasks_smoke.jsonl")
    smoke_types = {t["task_type"] for t in smoke_tasks}
    all_types = {t["task_type"] for t in tasks}
    if not all_types.issubset(smoke_types):
        fail(errors, f"smoke split missing task types: {sorted(all_types - smoke_types)}")

    assertion_roles = Counter(a.get("canonical_role") for a in assertions)
    task_counts = Counter(t["task_type"] for t in tasks)
    change_counts = Counter(c["family"] for c in changes)

    report = {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "counts": {
            "entities": len(entities),
            "assertion_events": len(assertions),
            "state_changes": len(changes),
            "contradiction_groups": len(contradictions),
            "tasks_total": len(tasks),
            "tasks_smoke": len(load_jsonl(GEN / "tasks_smoke.jsonl")),
            "tasks_dev": len(load_jsonl(GEN / "tasks_dev.jsonl")),
            "tasks_test": len(load_jsonl(GEN / "tasks_test.jsonl")),
            "ontology_versions": ontology_count,
            "policy_version_files": len(policy_files),
            "workflow_types": len(workflow_files),
        },
        "task_type_counts": dict(task_counts),
        "state_change_counts": dict(change_counts),
        "assertion_role_counts": dict(assertion_roles),
    }
    (OUT / "validation").mkdir(parents=True, exist_ok=True)
    (OUT / "validation" / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
