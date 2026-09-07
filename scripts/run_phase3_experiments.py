#!/usr/bin/env python3
"""Run Phase 3 retrieval, ablation, and execution-layer proxy experiments.

The runner is deterministic and standard-library only. It consumes the Phase 2
benchmark artifacts and writes auditable context packets, LLM-ready inputs,
proxy predictions, metrics, ablations, and bootstrap confidence intervals.
"""

from __future__ import annotations

import json
import math
import random
import re
import time
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lgr_operator import GovernanceBundle, admit_actions, evaluate_lgr, snapshot_manifest


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"
OUT = DATA / "phase3"
TOP_K = 8
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 2026061306
ACTION_ONLY_METRICS = {
    "action_exact_match_action_only",
    "llm_selected_action_valid_accuracy_action_only",
}

REQUIRED_METHODS = [
    "lexical_top_k_memory",
    "recency_weighted_memory",
    "ttl_only_memory",
    "temporal_kg_retrieval",
    "provenance_aware_kg_query",
    "ontology_versioned_retrieval",
    "graphrag_style_graph_retrieval",
    "event_sourced_latest_state_action",
    "lifecycle_governed_kg_retrieval",
]

ABLATIONS = [
    "lgr_no_lifecycle_state",
    "lgr_no_record_visibility",
    "lgr_no_validity_interval",
    "lgr_no_provenance_activity",
    "lgr_no_source_eligibility",
    "lgr_no_ontology_versioning",
    "lgr_no_policy_versioning",
    "lgr_no_supersession_links",
    "lgr_no_contradiction_resolver",
    "lgr_no_conflict_trust",
    "lgr_no_workflow_instance_scope",
    "lgr_no_action_target_binding",
    "lgr_no_bitemporal_checks",
    "lgr_no_workflow_scope_or_target_binding",
]

TRUST_PRECEDENCE = {
    "subscription_status": ["billing", "crm", "support_note", "generated_summary"],
    "account_owner": ["crm", "billing", "support_note", "generated_summary"],
    "support_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "product_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "contractual_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "sla_profile": ["billing", "crm", "support_note", "generated_summary"],
    "refund_rule": ["policy_registry", "support_note", "generated_summary"],
    "sla_rule": ["policy_registry", "support_note", "generated_summary"],
    "workflow_state": ["workflow_log", "support_note", "generated_summary"],
    "ticket_state": ["workflow_log", "support_note", "generated_summary"],
}

RELATION_ALIASES = {
    "support_plan": {"support_entitlement", "entitlement_profile", "support_plan"},
    "entitlement_profile": {"support_entitlement", "product_entitlement", "contractual_entitlement", "support_plan"},
    "support_entitlement": {"support_plan", "entitlement_profile", "support_entitlement"},
    "owner": {"account_owner", "owner"},
    "account_owner": {"owner", "account_owner"},
    "refund_status": {"workflow_state", "refund_status"},
    "workflow_state": {"refund_status", "workflow_state"},
}


def method_config(name: str) -> dict:
    base = {
        "name": name,
        "top_k": TOP_K,
        "strategy": "lgr",
        "ttl_days": None,
        "use_entity_scope": True,
        "use_relation_scope": True,
        "use_validity_interval": True,
        "use_record_visibility": True,
        "use_lifecycle_state": True,
        "use_provenance_trust": True,
        "use_provenance_activity": True,
        "use_source_eligibility": True,
        "use_ontology_versioning": True,
        "use_policy_versioning": True,
        "use_supersession_links": True,
        "use_contradiction_resolver": True,
        "use_conflict_trust": True,
        "use_workflow_state_binding": True,
        "use_workflow_instance_scope": True,
        "use_action_target_binding": True,
        "uses_oracle_fields": False,
        "no_dev_tuning": True,
    }
    if name == "lexical_top_k_memory":
        base.update(
            strategy="lexical_vector",
            use_entity_scope=False,
            use_relation_scope=False,
            use_validity_interval=False,
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "recency_weighted_memory":
        base.update(
            strategy="recency_weighted",
            use_validity_interval=False,
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "ttl_only_memory":
        base.update(
            strategy="ttl",
            ttl_days=60,
            use_validity_interval=False,
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "temporal_kg_retrieval":
        base.update(
            strategy="temporal",
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "provenance_aware_kg_query":
        base.update(
            strategy="provenance",
            use_lifecycle_state=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "ontology_versioned_retrieval":
        base.update(
            strategy="ontology",
            use_lifecycle_state=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "graphrag_style_graph_retrieval":
        base.update(
            strategy="graphrag",
            use_validity_interval=False,
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name == "event_sourced_latest_state_action":
        base.update(
            strategy="event_sourced_latest",
            use_validity_interval=False,
            use_lifecycle_state=False,
            use_provenance_trust=False,
            use_ontology_versioning=False,
            use_policy_versioning=False,
            use_supersession_links=False,
            use_contradiction_resolver=False,
            use_workflow_state_binding=False,
        )
    elif name in ABLATIONS:
        if name == "lgr_no_lifecycle_state":
            base["use_lifecycle_state"] = False
        elif name == "lgr_no_record_visibility":
            base["use_record_visibility"] = False
        elif name == "lgr_no_validity_interval":
            base["use_validity_interval"] = False
        elif name == "lgr_no_provenance_activity":
            base["use_provenance_activity"] = False
        elif name == "lgr_no_source_eligibility":
            base["use_source_eligibility"] = False
        elif name == "lgr_no_ontology_versioning":
            base["use_ontology_versioning"] = False
        elif name == "lgr_no_policy_versioning":
            base["use_policy_versioning"] = False
        elif name == "lgr_no_supersession_links":
            base["use_supersession_links"] = False
        elif name == "lgr_no_contradiction_resolver":
            base["use_contradiction_resolver"] = False
        elif name == "lgr_no_conflict_trust":
            base["use_conflict_trust"] = False
        elif name == "lgr_no_workflow_instance_scope":
            base["use_workflow_instance_scope"] = False
        elif name == "lgr_no_action_target_binding":
            base["use_action_target_binding"] = False
        elif name == "lgr_no_bitemporal_checks":
            base["use_record_visibility"] = False
            base["use_validity_interval"] = False
        elif name == "lgr_no_workflow_scope_or_target_binding":
            base["use_workflow_instance_scope"] = False
            base["use_action_target_binding"] = False
    return base


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def tokenize(value) -> set[str]:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def valid_at(assertion: dict, when: datetime) -> bool:
    start = parse_time(assertion.get("valid_from"))
    end = parse_time(assertion.get("valid_until"))
    if start and start > when:
        return False
    if end and end <= when:
        return False
    return True


def relation_matches(assertion: dict, task: dict, allow_alias: bool) -> bool:
    predicate = assertion.get("predicate")
    requested = set(task.get("relation_scope") or [])
    if predicate in requested:
        return True
    if not allow_alias:
        return False
    for rel in requested:
        if predicate in RELATION_ALIASES.get(rel, set()):
            return True
        if rel in RELATION_ALIASES.get(predicate, set()):
            return True
    return task.get("task_type") == "contradiction_handling" and assertion.get("contradiction_group")


def entity_matches(assertion: dict, task: dict) -> bool:
    scope = set(task.get("entity_scope") or [])
    assertion_scope = set(assertion.get("entity_scope") or [])
    if scope & assertion_scope:
        return True
    if assertion.get("subject") in scope:
        return True
    workflow_id = task.get("workflow_instance_id")
    return bool(workflow_id and assertion.get("workflow_instance_id") == workflow_id)


def ontology_compatible(assertion: dict, task: dict) -> bool:
    target = task.get("target_ontology_version")
    if assertion.get("ontology_version") == target:
        return True
    return relation_matches(assertion, task, allow_alias=True)


def policy_compatible(assertion: dict, task: dict) -> bool:
    if assertion.get("assertion_type") != "policy_fact":
        return True
    return assertion.get("policy_version") == task.get("target_policy_version")


def temporally_compatible(assertion: dict, task: dict) -> bool:
    if task.get("retrieval_mode") == "audit_historical":
        audit_time = parse_time(task.get("audit_time")) or parse_time(task["decision_time"])
        if valid_at(assertion, audit_time):
            return True
        return bool(assertion.get("supersedes") or assertion.get("superseded_by"))
    return valid_at(assertion, parse_time(task["decision_time"]))


def contradiction_winners(assertions: list[dict]) -> dict[str, str]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for assertion in assertions:
        group = assertion.get("contradiction_group")
        if group:
            groups[group].append(assertion)
    winners = {}
    for group, rows in groups.items():
        def key(row: dict):
            precedence = TRUST_PRECEDENCE.get(row.get("predicate"), [])
            source = row.get("source")
            source_rank = precedence.index(source) if source in precedence else len(precedence) + 1
            return (source_rank, parse_time(row.get("record_time")) or datetime.min.replace(tzinfo=timezone.utc), row["assertion_id"])

        winners[group] = sorted(rows, key=key)[0]["assertion_id"]
    return winners


def base_query_relevant(assertion: dict, task: dict) -> bool:
    return entity_matches(assertion, task) and relation_matches(assertion, task, allow_alias=True)


def exclusion_reason(assertion: dict, task: dict, cfg: dict, winners: dict[str, str]) -> str | None:
    if cfg["use_entity_scope"] and not entity_matches(assertion, task):
        return "entity_scope_mismatch"
    if cfg["use_relation_scope"] and not relation_matches(assertion, task, allow_alias=cfg["use_ontology_versioning"]):
        return "relation_scope_mismatch"
    if cfg["ttl_days"] is not None:
        decision_time = parse_time(task["decision_time"])
        record_time = parse_time(assertion.get("record_time"))
        if record_time and record_time < decision_time - timedelta(days=cfg["ttl_days"]):
            return "ttl_expired"
    if cfg["use_validity_interval"] and not temporally_compatible(assertion, task):
        return "not_valid_at_query_time"
    if cfg["use_lifecycle_state"]:
        if task.get("retrieval_mode") == "audit_historical":
            if assertion.get("lifecycle_state") != "active" and assertion.get("predicate") != "support_plan":
                return "inactive_lifecycle_state"
        elif assertion.get("lifecycle_state") != "active":
            return "inactive_lifecycle_state"
    if cfg["use_supersession_links"] and task.get("retrieval_mode") != "audit_historical":
        if assertion.get("superseded_by"):
            return "superseded_by_newer_assertion"
    if cfg["use_provenance_trust"]:
        if not assertion.get("source") or assertion.get("source") in set(task.get("disallowed_sources") or []):
            return "missing_or_disallowed_provenance"
    if cfg["use_ontology_versioning"] and not ontology_compatible(assertion, task):
        return "ontology_version_incompatible"
    if cfg["use_policy_versioning"] and not policy_compatible(assertion, task):
        return "policy_version_incompatible"
    if cfg["use_workflow_state_binding"]:
        workflow_id = task.get("workflow_instance_id")
        if assertion.get("workflow_instance_id") and workflow_id and assertion.get("workflow_instance_id") != workflow_id:
            return "workflow_instance_mismatch"
    if cfg["use_contradiction_resolver"]:
        group = assertion.get("contradiction_group")
        if group and winners.get(group) != assertion["assertion_id"]:
            return "contradiction_loser"
    return None


def score_for_rank(assertion: dict, task: dict, cfg: dict) -> float:
    q_tokens = tokenize(
        {
            "question": task.get("natural_language_question"),
            "relations": task.get("relation_scope"),
            "entities": task.get("entity_scope"),
            "actions": task.get("candidate_actions"),
        }
    )
    a_tokens = tokenize(
        {
            "subject": assertion.get("subject"),
            "predicate": assertion.get("predicate"),
            "object": assertion.get("object"),
            "type": assertion.get("assertion_type"),
            "source": assertion.get("source"),
        }
    )
    score = len(q_tokens & a_tokens) / math.sqrt(max(len(a_tokens), 1))
    if entity_matches(assertion, task):
        score += 4.0
    if assertion.get("predicate") in set(task.get("relation_scope") or []):
        score += 4.0
    elif relation_matches(assertion, task, allow_alias=True):
        score += 2.0
    if assertion.get("source") in {"billing", "crm", "workflow_log", "policy_registry"}:
        score += 0.5
    if cfg["strategy"] in {"recency_weighted", "graphrag", "event_sourced_latest"}:
        decision_time = parse_time(task["decision_time"])
        record_time = parse_time(assertion.get("record_time")) or decision_time
        age_days = max((decision_time - record_time).total_seconds() / 86400.0, 0.0)
        score += 2.0 / (1.0 + age_days)
    if cfg["strategy"] == "lexical_vector":
        return score
    if cfg["strategy"] == "lgr" and assertion.get("lifecycle_state") == "active":
        score += 1.0
    return score


def latest_per_predicate(assertions: list[dict]) -> list[dict]:
    latest: dict[tuple[str, str | None], dict] = {}
    for assertion in assertions:
        key = (assertion.get("predicate"), assertion.get("workflow_instance_id") or assertion.get("subject"))
        old = latest.get(key)
        if not old or (assertion.get("record_time"), assertion["assertion_id"]) > (old.get("record_time"), old["assertion_id"]):
            latest[key] = assertion
    return list(latest.values())


def retrieve(
    method: str,
    split: str,
    task: dict,
    assertions: list[dict],
    winners: dict[str, str],
    governance: GovernanceBundle,
    snapshot: dict,
) -> dict:
    cfg = method_config(method)
    started = time.perf_counter()
    query_relevant = [a for a in assertions if base_query_relevant(a, task)]
    candidates: list[dict] = []
    if cfg["strategy"] == "lgr":
        initial_evaluation = evaluate_lgr(assertions, task, cfg, governance, top_k=cfg["top_k"])
        top = initial_evaluation["packet_assertions"]
    else:
        candidates: list[dict] = []
        for assertion in assertions:
            reason = exclusion_reason(assertion, task, cfg, winners)
            if reason:
                continue
            if cfg["strategy"] == "lexical_vector":
                if score_for_rank(assertion, task, cfg) <= 0:
                    continue
            candidates.append(assertion)

        if cfg["strategy"] == "graphrag":
            graph_seed = set(task.get("entity_scope") or [])
            expanded = []
            for assertion in assertions:
                if graph_seed & (set(assertion.get("entity_scope") or []) | {assertion.get("subject")}):
                    expanded.append(assertion)
            candidates = [a for a in expanded if exclusion_reason(a, task, cfg, winners) is None]
        elif cfg["strategy"] == "event_sourced_latest":
            candidates = latest_per_predicate([a for a in candidates if base_query_relevant(a, task)])

        ranked = sorted(
            candidates,
            key=lambda a: (score_for_rank(a, task, cfg), a.get("record_time") or "", a["assertion_id"]),
            reverse=True,
        )
        top = ranked[: cfg["top_k"]]

    # All main-comparison generators are measured at the same context budget,
    # but their proposed actions are checked against the same authoritative
    # decision closure. Ablations intentionally change that operator.
    gate_cfg = cfg if method in ABLATIONS else method_config("lifecycle_governed_kg_retrieval")
    evaluated = evaluate_lgr(assertions, task, gate_cfg, governance, top_k=cfg["top_k"])
    suppression_reason_lists = evaluated["suppression_reasons"]
    suppressed = {
        assertion_id: reasons[0]
        for assertion_id, reasons in suppression_reason_lists.items()
        if reasons
    }
    unresolved_conflicts = evaluated["unresolved_conflicts"]
    conflict_trace = evaluated["conflict_trace"]
    admission = {
        "valid_actions": evaluated["valid_actions"],
        "blocked_actions": evaluated["blocked_actions"],
        "blocking_reasons": evaluated["blocking_reasons"],
        "support_by_action": evaluated["support_by_action"],
        "bindings_consulted": evaluated["bindings_consulted"],
    }

    packet = {
        "packet_id": f"{split}:{method}:{task['task_id']}",
        "task_id": task["task_id"],
        "split": split,
        "method": method,
        "feature_mask": feature_mask(cfg),
        "retrieved_assertion_ids": [a["assertion_id"] for a in top],
        "initial_retrieved_assertion_ids": [a["assertion_id"] for a in top],
        "decision_evidence_assertion_ids": evaluated["decision_evidence_completion"]["assertion_ids"],
        "decision_evidence_status": evaluated["decision_evidence_completion"]["status"],
        "initial_retrieval_budget": cfg["top_k"],
        "decision_evidence_count": len(evaluated["decision_evidence"]),
        "retrieved_assertions": [sanitize_assertion(a, cfg) for a in top],
        "suppressed_assertion_ids": sorted(suppressed),
        "suppression_reasons": suppressed,
        "suppression_reason_lists": suppression_reason_lists,
        "predicted_valid_actions": admission["valid_actions"],
        "predicted_blocked_actions": admission["blocked_actions"],
        "action_support_by_action": admission["support_by_action"],
        "blocked_action_reasons": admission["blocking_reasons"],
        "bindings_consulted": admission["bindings_consulted"],
        "unresolved_conflicts": unresolved_conflicts,
        "conflict_trace": conflict_trace,
        "provenance_trace": [
            {
                "assertion_id": row["assertion_id"],
                "source": row.get("source"),
                "provenance_activity": row.get("provenance_activity"),
            }
            for row in top
        ],
        "audit_trace": [
            {"assertion_id": assertion_id, "reasons": reasons}
            for assertion_id, reasons in sorted(suppression_reason_lists.items())
        ],
        "snapshot_id": snapshot["snapshot_id"],
        "append_log_checkpoint": snapshot["append_log_checkpoint"],
        "query_relevant_candidate_count": len(query_relevant),
        "retrieval_latency_ms": round((time.perf_counter() - started) * 1000.0, 4),
    }
    packet["token_count_estimate"] = estimate_tokens(packet["retrieved_assertions"])
    return packet


def feature_mask(cfg: dict) -> dict:
    return {
        "mask_version": "phase3_feature_masks_v2",
        "oracle_fields_visible": False,
        "gold_fields_visible": False,
        "current_workflow_state_visible_to_llm": False,
        "use_lifecycle_state": cfg["use_lifecycle_state"],
        "use_validity_interval": cfg["use_validity_interval"],
        "use_record_visibility": cfg["use_record_visibility"],
        "use_provenance_trust": cfg["use_provenance_trust"],
        "use_provenance_activity": cfg["use_provenance_activity"],
        "use_source_eligibility": cfg["use_source_eligibility"],
        "use_ontology_versioning": cfg["use_ontology_versioning"],
        "use_policy_versioning": cfg["use_policy_versioning"],
        "use_supersession_links": cfg["use_supersession_links"],
        "use_contradiction_resolver": cfg["use_contradiction_resolver"],
        "use_conflict_trust": cfg["use_conflict_trust"],
        "use_workflow_state_binding": cfg["use_workflow_state_binding"],
        "use_workflow_instance_scope": cfg["use_workflow_instance_scope"],
        "use_action_target_binding": cfg["use_action_target_binding"],
    }


def sanitize_assertion(assertion: dict, cfg: dict) -> dict:
    row = {
        "assertion_id": assertion["assertion_id"],
        "subject": assertion.get("subject"),
        "predicate": assertion.get("predicate"),
        "object": assertion.get("object"),
        "assertion_type": assertion.get("assertion_type"),
        "event_time": assertion.get("event_time"),
        "record_time": assertion.get("record_time"),
    }
    if cfg["use_entity_scope"]:
        row["entity_scope"] = assertion.get("entity_scope")
    if cfg["use_validity_interval"]:
        row["valid_from"] = assertion.get("valid_from")
        row["valid_until"] = assertion.get("valid_until")
    if cfg["use_ontology_versioning"]:
        row["ontology_version"] = assertion.get("ontology_version")
    if cfg["use_policy_versioning"]:
        row["policy_version"] = assertion.get("policy_version")
    if cfg["use_provenance_trust"]:
        row["source"] = assertion.get("source")
        row["trust_class"] = assertion.get("trust_class")
        row["provenance_activity"] = assertion.get("provenance_activity")
    if cfg["use_lifecycle_state"]:
        row["lifecycle_state"] = assertion.get("lifecycle_state")
    if cfg["use_supersession_links"]:
        row["supersedes"] = assertion.get("supersedes")
        row["superseded_by"] = assertion.get("superseded_by")
    if cfg["use_contradiction_resolver"]:
        row["contradiction_group"] = assertion.get("contradiction_group")
    if cfg["use_workflow_state_binding"]:
        row["workflow_instance_id"] = assertion.get("workflow_instance_id")
        row["workflow_state_binding"] = assertion.get("workflow_state_binding")
    return row


def estimate_tokens(assertions: list[dict]) -> int:
    return max(1, len(json.dumps(assertions, sort_keys=True)) // 4)


def facts_from_assertions(assertions: list[dict]) -> dict[str, str]:
    facts = {}
    for assertion in sorted(assertions, key=lambda a: (a.get("record_time") or "", a["assertion_id"])):
        pred = assertion.get("predicate")
        if pred:
            facts[pred] = assertion.get("object")
    return facts


def proxy_llm_output(packet: dict, task: dict) -> dict:
    assertions = packet["retrieved_assertions"]
    facts = facts_from_assertions(assertions)
    selected = packet["predicted_valid_actions"][0] if packet["predicted_valid_actions"] else None
    support_ids = []
    for assertion in assertions:
        if assertion.get("predicate") in set(task.get("relation_scope") or []) or relation_matches(assertion, task, allow_alias=True):
            support_ids.append(assertion["assertion_id"])
    support_ids = support_ids[:4]
    if task["task_type"] == "workflow_state_next_action":
        answer = facts.get("workflow_state", "unknown")
    elif task["task_type"] in {"policy_valid_refund_action", "sla_valid_escalation_action"}:
        answer = "valid_action_available" if selected else "all_actions_blocked"
    elif task["task_type"] == "contradiction_handling":
        answer = "unique_winner" if any(a.get("contradiction_group") for a in assertions) else "no_trusted_winner_found"
    elif task["task_type"] == "audit_valid_historical_explanation":
        answer = "historical_explanation" if len(support_ids) >= 2 else "incomplete_historical_trace"
    else:
        answer = "unknown"
        for assertion in assertions:
            if relation_matches(assertion, task, allow_alias=True):
                answer = str(assertion.get("object"))
                break
    return {
        "task_id": task["task_id"],
        "method": packet["method"],
        "answer": answer,
        "selected_action": selected,
        "support_assertion_ids": support_ids,
        "blocked_action_ids": packet["predicted_blocked_actions"],
        "confidence": 0.8 if support_ids else 0.2,
        "rationale": "Deterministic execution-layer proxy over retrieved packet fields.",
    }


def llm_input(packet: dict, task: dict) -> dict:
    task_view = {
        "task_id": task["task_id"],
        "task_type": task["task_type"],
        "natural_language_question": task["natural_language_question"],
        "decision_time": task["decision_time"],
        "entity_scope": task.get("entity_scope"),
        "entity_scope_mode": task.get("entity_scope_mode"),
        "target_ontology_version": task.get("target_ontology_version"),
        "target_policy_version": task.get("target_policy_version"),
        "retrieval_mode": task.get("retrieval_mode"),
        "candidate_actions": task.get("candidate_actions"),
        "assertion_templates": task.get("assertion_templates"),
    }
    return {
        "packet_id": packet["packet_id"],
        "task_id": task["task_id"],
        "split": packet["split"],
        "method": packet["method"],
        "task_view": task_view,
        "retrieved_assertions": packet["retrieved_assertions"],
        "output_schema": ["task_id", "method", "answer", "selected_action", "support_assertion_ids", "blocked_action_ids", "confidence", "rationale"],
    }


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def f1(precision: float, recall: float) -> float:
    return safe_div(2 * precision * recall, precision + recall)


def score_packet(packet: dict, pred: dict, task: dict, gold: dict, assertion_by_id: dict[str, dict]) -> dict:
    retrieved = set(packet["retrieved_assertion_ids"])
    eligible = set(gold.get("eligible_assertion_ids") or [])
    stale = set(gold.get("stale_or_superseded_assertion_ids") or []) - eligible
    suppression_gold = gold.get("expected_suppression") or {}
    contradiction_losers = {aid for aid, reasons in suppression_gold.items() if "contradiction_loser" in reasons}
    precision = safe_div(len(retrieved & eligible), len(retrieved))
    recall = safe_div(len(retrieved & eligible), len(eligible))
    temporal_ok = [aid for aid in retrieved if temporally_compatible(assertion_by_id[aid], task)]
    compatible_ok = [aid for aid in retrieved if entity_matches(assertion_by_id[aid], task) and relation_matches(assertion_by_id[aid], task, allow_alias=True)]
    suppressed = set(packet.get("suppressed_assertion_ids") or [])
    superseded_tp = len(suppressed & stale)
    superseded_fp = len(suppressed - stale)
    superseded_fn = len(stale - suppressed - retrieved)
    superseded_precision = safe_div(superseded_tp, superseded_tp + superseded_fp)
    superseded_recall = safe_div(superseded_tp, superseded_tp + superseded_fn)
    valid_gold = set(gold.get("valid_actions") or [])
    blocked_gold = set(gold.get("blocked_actions") or [])
    valid_pred = set(packet.get("predicted_valid_actions") or [])
    selected = pred.get("selected_action")
    support = set(pred.get("support_assertion_ids") or [])
    support_sets = gold.get("acceptable_llm_outputs", {}).get("required_support_sets", [])
    action_task = bool(task.get("candidate_actions"))
    policy_task = task["task_type"] == "policy_valid_refund_action"
    workflow_task = task["task_type"] in {"policy_valid_refund_action", "sla_valid_escalation_action", "workflow_state_next_action"}
    support_packet_precision = safe_div(len(support & retrieved), len(support))
    return {
        "task_id": task["task_id"],
        "task_type": task["task_type"],
        "method": packet["method"],
        "eligible_precision": precision,
        "eligible_recall": recall,
        "eligible_f1": f1(precision, recall),
        "stale_suppression_recall": safe_div(len(stale - retrieved), len(stale)) if stale else 1.0,
        "stale_exposure_rate": safe_div(len(stale & retrieved), len(stale)) if stale else 0.0,
        "temporal_validity_consistency": safe_div(len(temporal_ok), len(retrieved)),
        "version_entity_relation_accuracy": safe_div(len(compatible_ok), len(retrieved)),
        "contradiction_loser_suppression_recall": safe_div(len(contradiction_losers - retrieved), len(contradiction_losers)) if contradiction_losers else 1.0,
        "contradiction_winner_recall": safe_div(len(retrieved & set(gold.get("contradiction_winner_ids") or [])), len(set(gold.get("contradiction_winner_ids") or []))) if gold.get("contradiction_winner_ids") else 1.0,
        "provenance_constrained_accuracy": 1.0 if all(assertion_by_id[aid].get("source") for aid in retrieved & eligible) else 0.0,
        "supersession_detection_f1": f1(superseded_precision, superseded_recall),
        "policy_valid_action_accuracy": 1.0 if policy_task and valid_pred == valid_gold else (None if not policy_task else 0.0),
        "workflow_state_eligibility_accuracy": 1.0 if workflow_task and valid_pred == valid_gold else (None if not workflow_task else 0.0),
        "action_exact_match_action_only": 1.0 if action_task and valid_pred == valid_gold else (None if not action_task else 0.0),
        "audit_trace_completeness": recall if task["task_type"] == "audit_valid_historical_explanation" else None,
        "llm_answer_accuracy": 1.0 if pred.get("answer") == gold.get("answer_class") else 0.0,
        "llm_selected_action_valid_accuracy_action_only": 1.0 if action_task and ((selected in valid_gold) or (selected is None and not valid_gold)) else (None if not action_task else 0.0),
        "llm_invalid_action_rate_action_only": 1.0 if action_task and (selected in blocked_gold or (selected is not None and selected not in set(task.get("candidate_actions") or []))) else (None if not action_task else 0.0),
        "cited_assertion_support_precision": support_packet_precision,
        "hallucinated_assertion_rate": 1.0 - support_packet_precision if support else 0.0,
        "blocked_action_correctness_action_only": 1.0 if action_task and blocked_gold.issubset(set(pred.get("blocked_action_ids") or [])) else (None if not action_task else 0.0),
        "support_complete_set_rate": 1.0 if any(set(sset).issubset(support) for sset in support_sets) else 0.0,
        "token_count_estimate": packet["token_count_estimate"],
        "retrieval_latency_ms": packet["retrieval_latency_ms"],
        "end_to_end_proxy_latency_ms": packet["retrieval_latency_ms"],
    }


def aggregate(rows: list[dict]) -> dict:
    metrics = defaultdict(list)
    for row in rows:
        for key, value in row.items():
            if key in {"task_id", "task_type", "method"} or value is None:
                continue
            if isinstance(value, (int, float)):
                metrics[key].append(float(value))
    report = {"tasks": len(rows)}
    for key, values in sorted(metrics.items()):
        report[key] = sum(values) / len(values) if values else None
    action_rows = [r for r in rows if r.get("action_exact_match_action_only") is not None]
    report["action_tasks"] = len(action_rows)
    return report


def aggregate_by_task_type(rows: list[dict]) -> dict:
    by_type = defaultdict(list)
    for row in rows:
        by_type[row["task_type"]].append(row)
    return {task_type: aggregate(items) for task_type, items in sorted(by_type.items())}


def bootstrap_ci(per_task: list[dict], metrics: list[str]) -> dict:
    rng = random.Random(BOOTSTRAP_SEED)
    methods = sorted({row["method"] for row in per_task})
    by_method_task = defaultdict(dict)
    for row in per_task:
        by_method_task[row["method"]][row["task_id"]] = row
    task_ids = sorted({row["task_id"] for row in per_task if row["method"] == "lifecycle_governed_kg_retrieval"})
    result = {}
    for metric in metrics:
        # Every implemented non-LGR method is eligible to be the comparison
        # baseline for every metric it reports.  Excluding a method here while
        # still listing its score in the main table would report a difference
        # against something other than the strongest implemented baseline.
        baselines = [m for m in REQUIRED_METHODS if m != "lifecycle_governed_kg_retrieval"]
        baseline_means = {}
        for method in baselines:
            values = [by_method_task[method][tid].get(metric) for tid in task_ids if by_method_task[method][tid].get(metric) is not None]
            if values:
                baseline_means[method] = sum(values) / len(values)
        if not baseline_means:
            continue
        best_baseline = max(baseline_means, key=baseline_means.get)
        diffs = []
        valid_tids = [
            tid
            for tid in task_ids
            if by_method_task["lifecycle_governed_kg_retrieval"][tid].get(metric) is not None
            and by_method_task[best_baseline][tid].get(metric) is not None
        ]
        if not valid_tids:
            continue
        for _ in range(BOOTSTRAP_SAMPLES):
            sample = [rng.choice(valid_tids) for _ in valid_tids]
            lgr = [by_method_task["lifecycle_governed_kg_retrieval"][tid][metric] for tid in sample]
            base = [by_method_task[best_baseline][tid][metric] for tid in sample]
            diffs.append(sum(lgr) / len(lgr) - sum(base) / len(base))
        diffs.sort()
        result[metric] = {
            "lgr_minus_best_baseline_mean": sum(diffs) / len(diffs),
            "ci95_low": diffs[int(0.025 * len(diffs))],
            "ci95_high": diffs[int(0.975 * len(diffs))],
            "best_baseline": best_baseline,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
        }
    return result


def markdown_table(title: str, methods: list[str], metrics_by_method: dict[str, dict], metric_names: list[str]) -> str:
    lines = [f"# {title}", "", "| Method | " + " | ".join(metric_names) + " |", "|---|" + "|".join(["---:"] * len(metric_names)) + "|"]
    for method in methods:
        report = metrics_by_method[method]
        vals = []
        for name in metric_names:
            value = report.get(name)
            vals.append("n/a" if value is None else f"{value:.3f}")
        lines.append("| " + method + " | " + " | ".join(vals) + " |")
    lines.append("")
    return "\n".join(lines)


def run_split(
    split: str,
    assertions: list[dict],
    assertion_by_id: dict[str, dict],
    winners: dict[str, str],
    governance: GovernanceBundle,
    snapshot: dict,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    tasks = load_jsonl(GEN / f"tasks_{split}.jsonl")
    gold_by_task = {row["task_id"]: row for row in load_jsonl(GEN / f"gold_{split}.jsonl")}
    all_methods = REQUIRED_METHODS + ABLATIONS
    packets = []
    inputs = []
    proxy_preds = []
    scored = []
    for method in all_methods:
        for task in tasks:
            packet = retrieve(method, split, task, assertions, winners, governance, snapshot)
            pred = proxy_llm_output(packet, task)
            packets.append(packet)
            inputs.append(llm_input(packet, task))
            proxy_preds.append(pred)
            scored.append(score_packet(packet, pred, task, gold_by_task[task["task_id"]], assertion_by_id))
    metrics_by_method = {method: aggregate([row for row in scored if row["method"] == method]) for method in all_methods}
    by_task_type = {
        method: aggregate_by_task_type([row for row in scored if row["method"] == method])
        for method in all_methods
    }
    write_jsonl(OUT / f"context_packets_{split}.jsonl", packets)
    write_jsonl(OUT / f"llm_inputs_{split}.jsonl", inputs)
    write_jsonl(OUT / f"llm_proxy_predictions_{split}.jsonl", proxy_preds)
    write_jsonl(OUT / f"per_task_metrics_{split}.jsonl", scored)
    write_json(OUT / f"metrics_{split}.json", metrics_by_method)
    write_json(OUT / f"metrics_by_task_type_{split}.json", by_task_type)
    return packets, proxy_preds, scored, metrics_by_method


def main(data_root: Path | None = None, output_dir: Path | None = None) -> int:
    global DATA, GEN, OUT
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        parser.add_argument("--output-dir", type=Path)
        args = parser.parse_args()
        data_root, output_dir = args.data_root, args.output_dir
    DATA = data_root.resolve()
    GEN = DATA / "generated"
    OUT = output_dir.resolve() if output_dir else DATA / "phase3"
    OUT.mkdir(parents=True, exist_ok=True)
    assertions = load_jsonl(GEN / "assertion_events.jsonl")
    assertion_by_id = {row["assertion_id"]: row for row in assertions}
    winners = contradiction_winners(assertions)
    governance = GovernanceBundle.load(DATA)
    snapshot = snapshot_manifest(DATA)
    write_json(OUT / "snapshot_manifest.json", snapshot)

    test_scored = []
    metrics = {}
    for split in ["smoke", "dev", "test"]:
        _, _, scored, metrics_by_method = run_split(
            split,
            assertions,
            assertion_by_id,
            winners,
            governance,
            snapshot,
        )
        if split == "test":
            test_scored = scored
        metrics[split] = metrics_by_method

    write_json(
        OUT / "phase3_config.json",
        {
            "phase": 3,
            "top_k": TOP_K,
            "methods": {name: method_config(name) for name in REQUIRED_METHODS + ABLATIONS},
            "no_dev_tuning": True,
            "dev_split_use": "debug/smoke only; all method definitions and thresholds are fixed before reading results",
            "oracle_fields_forbidden_in_retrieval": ["canonical_role"],
            "llm_task_view_masks": ["current_workflow_state", "valid_actions", "blocked_actions", "expected_suppression", "canonical_role"],
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
        },
    )
    ci = bootstrap_ci(
        [row for row in test_scored if row["method"] in REQUIRED_METHODS and row.get("task_id")],
        [
            "eligible_f1",
            "stale_suppression_recall",
            "contradiction_loser_suppression_recall",
            "action_exact_match_action_only",
            "llm_selected_action_valid_accuracy_action_only",
        ],
    )
    write_json(OUT / "confidence_intervals_test.json", ci)
    write_json(
        OUT / "run_manifest.json",
        {
            # Names only: absolute paths would leak the builder's local
            # directory layout into a published artifact.
            "generated_files": sorted(p.name for p in OUT.glob("*")),
            "splits": ["smoke", "dev", "test"],
            "required_methods": REQUIRED_METHODS,
            "ablations": ABLATIONS,
            "real_llm_runs": False,
            "real_llm_run_note": "OPENAI_API_KEY was not set in the local environment; Phase 3 includes LLM-ready inputs and deterministic proxy outputs.",
        },
    )
    main_metrics = [
        "eligible_f1",
        "stale_suppression_recall",
        "contradiction_loser_suppression_recall",
        "action_exact_match_action_only",
        "llm_selected_action_valid_accuracy_action_only",
        "token_count_estimate",
        "retrieval_latency_ms",
    ]
    (OUT / "main_results_table.md").write_text(
        markdown_table("Phase 3 Main Test Results", REQUIRED_METHODS, metrics["test"], main_metrics),
        encoding="utf-8",
    )
    (OUT / "ablation_table.md").write_text(
        markdown_table("Phase 3 LGR Ablation Test Results", ["lifecycle_governed_kg_retrieval"] + ABLATIONS, metrics["test"], main_metrics),
        encoding="utf-8",
    )
    print(json.dumps({"status": "pass", "output_dir": str(OUT), "test_lgr": metrics["test"]["lifecycle_governed_kg_retrieval"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
