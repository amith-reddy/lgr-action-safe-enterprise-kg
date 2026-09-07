#!/usr/bin/env python3
"""Generate the EvoMem-Enterprise Phase 2 benchmark artifacts.

The generator is deterministic and standard-library only. It creates:
- executable schemas/config/policies/workflows/ontologies
- generated entities, canonical state timelines, state changes, assertion events
- contradiction groups
- smoke/dev/test task splits
- gold labels independent of the LGR implementation
- prompt template and README
"""

from __future__ import annotations

import json
import random
import argparse
import hashlib
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "evomem_enterprise"

SEEDS = {
    "seed_entities": 2026061301,
    "seed_events": 2026061302,
    "seed_contradictions": 2026061303,
    "seed_tasks": 2026061304,
    "seed_splits": 2026061305,
}

BASE_TIME = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
DECISION_TIME = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)

PLAN_VALUES = ["Basic", "Standard", "Premium", "EnterprisePlus"]
STATUSES = ["active", "suspended", "cancelled"]
REGIONS = ["NA", "EU", "APAC", "LATAM", "MEA", "ANZ"]
SEVERITIES = ["low", "medium", "high", "critical"]
AMOUNT_BANDS = ["low", "medium", "high"]
REFUND_REASONS = ["billing_error", "service_outage", "duplicate_charge", "contract_exception"]

TRUST_PRECEDENCE = {
    "subscription_status": ["billing", "crm", "support_note", "generated_summary"],
    "account_owner": ["crm", "billing", "support_note", "generated_summary"],
    "support_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "product_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "contractual_entitlement": ["billing", "crm", "support_note", "generated_summary"],
    "sla_profile": ["billing", "crm", "support_note", "generated_summary"],
    "refund_amount": ["billing", "support_note", "generated_summary"],
    "support_plan": ["billing", "crm", "support_note", "generated_summary"],
    "ticket_severity": ["workflow_log", "support_note", "generated_summary"],
    "refund_rule": ["policy_registry", "support_note", "generated_summary"],
    "sla_rule": ["policy_registry", "support_note", "generated_summary"],
    "workflow_state": ["workflow_log", "support_note", "generated_summary"],
    "ticket_state": ["workflow_log", "support_note", "generated_summary"],
}


def conflict_semantics() -> dict:
    """Versioned relation-level definition of decision-variable conflicts."""
    relations = {
        relation: {
            "cardinality": "single_value",
            "key": "workflow_or_subject" if relation in {"refund_amount", "refund_rule", "sla_rule", "ticket_severity", "ticket_state", "workflow_state"} else "subject",
            "incompatibility": "distinct_values",
        }
        for relation in TRUST_PRECEDENCE
    }
    relations["support_contact"] = {
        "cardinality": "multi_value",
        "key": "subject",
        "incompatibility": "none",
    }
    return {"version": "conflict-semantics-v1", "relations": relations}


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def nid(prefix: str, i: int) -> str:
    return f"{prefix}_{i:03d}"


def resolve_declared_conflict(
    assertion_ids: list[str],
    assertion_by_id: dict[str, dict],
    relation: str,
    query_time: str,
    trust: dict[str, list[str]] | None = None,
) -> list[str]:
    """Independent label-side trust/time resolution for one single-value key."""
    tiers = (trust or TRUST_PRECEDENCE).get(relation, [])
    rows = [
        assertion_by_id[assertion_id]
        for assertion_id in assertion_ids
        if assertion_id in assertion_by_id
        and assertion_by_id[assertion_id].get("predicate") == relation
        and (assertion_by_id[assertion_id].get("record_time") or "") <= query_time
        and assertion_by_id[assertion_id].get("lifecycle_state") == "active"
        and assertion_by_id[assertion_id].get("source") in tiers
    ]
    if not rows:
        return []
    best_rank = min(tiers.index(row["source"]) for row in rows)
    trusted = [row for row in rows if tiers.index(row["source"]) == best_rank]
    newest = max(row.get("record_time") or "" for row in trusted)
    finalists = [row for row in trusted if (row.get("record_time") or "") == newest]
    values = {json.dumps(row.get("object"), sort_keys=True) for row in finalists}
    if len(values) != 1:
        return []
    return sorted(row["assertion_id"] for row in finalists)


def derived_seeds(master_seed: int) -> dict[str, int]:
    """Derive stable, independent RNG streams without Python's salted hash()."""
    return {
        name: int.from_bytes(
            hashlib.sha256(f"evomem-v3:{master_seed}:{name}".encode("utf-8")).digest()[:8],
            "big",
        )
        for name in SEEDS
    }


class Gen:
    def __init__(
        self,
        *,
        output_root: Path = OUT,
        seeds: dict[str, int] | None = None,
        world_id: str = "world-original",
        benchmark_version: str = "phase2-minimum-v2",
    ) -> None:
        self.output_root = output_root
        self.seeds = dict(seeds or SEEDS)
        self.world_id = world_id
        self.benchmark_version = benchmark_version
        self.rng_entities = random.Random(self.seeds["seed_entities"])
        self.rng_events = random.Random(self.seeds["seed_events"])
        self.rng_contra = random.Random(self.seeds["seed_contradictions"])
        self.rng_tasks = random.Random(self.seeds["seed_tasks"])
        self.entities = []
        self.entity_ids = {}
        self.assertions = []
        self.state_changes = []
        self.canonical = []
        self.contradiction_groups = []
        self.tasks = []
        self.gold = []
        self.account = {}
        self.refund_cases = {}
        self.ticket_cases = {}
        self.assertion_counter = 1
        self.state_counter = 1
        self.contradiction_counter = 1
        self.task_counter = 1

    def add_entity(self, entity_type: str, entity_id: str, **attrs) -> str:
        row = {"entity_id": entity_id, "entity_type": entity_type, **attrs}
        self.entities.append(row)
        self.entity_ids.setdefault(entity_type, []).append(entity_id)
        return entity_id

    def add_assertion(
        self,
        *,
        subject: str,
        predicate: str,
        obj,
        assertion_type: str = "semantic_fact",
        entity_scope=None,
        relation_scope=None,
        event_time=None,
        record_time=None,
        valid_from=None,
        valid_until=None,
        ontology_version="ov_3",
        policy_version="refund_policy_v2",
        provenance_activity=None,
        source="billing",
        trust_class=None,
        lifecycle_state="active",
        supersedes=None,
        superseded_by=None,
        contradiction_group=None,
        workflow_instance_id=None,
        workflow_state_binding=None,
        canonical_role="current",
    ) -> str:
        aid = f"a_{self.assertion_counter:05d}"
        self.assertion_counter += 1
        source_or_none = None if source == "none" else source
        row = {
            "assertion_id": aid,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "assertion_type": assertion_type,
            "entity_scope": entity_scope or [subject],
            "relation_scope": relation_scope or [predicate],
            "event_time": iso(event_time or DECISION_TIME),
            "record_time": iso(record_time or (event_time or DECISION_TIME) + timedelta(minutes=5)),
            "valid_from": iso(valid_from or BASE_TIME),
            "valid_until": iso(valid_until) if valid_until else None,
            "ontology_version": ontology_version,
            "policy_version": policy_version,
            "provenance_activity": provenance_activity or (f"pa_{aid}" if source_or_none else None),
            "source": source_or_none,
            "trust_class": trust_class or source_or_none,
            "lifecycle_state": lifecycle_state,
            "supersedes": supersedes or [],
            "superseded_by": superseded_by or [],
            "contradiction_group": contradiction_group,
            "workflow_instance_id": workflow_instance_id,
            "workflow_state_binding": workflow_state_binding,
            "canonical_role": canonical_role,
        }
        self.assertions.append(row)
        return aid

    def add_state_change(self, family: str, subject: str, before, after, t: datetime, **attrs) -> str:
        sid = f"sc_{self.state_counter:05d}"
        self.state_counter += 1
        row = {
            "state_change_id": sid,
            "family": family,
            "subject": subject,
            "before": before,
            "after": after,
            "event_time": iso(t),
            **attrs,
        }
        self.state_changes.append(row)
        self.canonical.append(row)
        return sid

    def build_static_artifacts(self) -> None:
        (self.output_root / "prompts").mkdir(parents=True, exist_ok=True)
        write_json(self.output_root / "config" / "seeds.yaml", self.seeds)
        write_json(
            self.output_root / "config" / "benchmark_config.yaml",
            {
                "benchmark": "EvoMem-Enterprise",
                "version": self.benchmark_version,
                "world_id": self.world_id,
                "date_range": {"start": iso(BASE_TIME), "decision": iso(DECISION_TIME)},
                "closed_world": True,
                "minimums": {
                    "entity_nodes": 100,
                    "assertion_events": 500,
                    "state_change_events": 100,
                    "evaluation_tasks": 100,
                    "ontology_versions": 3,
                    "policy_families": 2,
                    "contradiction_cases": 50,
                    "workflow_types": 2,
                },
                "seeds": self.seeds,
            },
        )
        self.write_schemas()
        self.write_ontologies()
        self.write_governance_config()
        self.write_policies()
        self.write_workflows()
        (self.output_root / "prompts" / "llm_action_eval_prompt.txt").write_text(
            "You are given a masked task view and a retrieved assertion packet. Use only assertion ids in the packet. "
            "The task view may include candidate actions but never includes gold valid actions, gold blocked actions, "
            "suppression labels, current workflow state, or oracle-only fields. "
            "Return JSON only with task_id, method, answer, selected_action, support_assertion_ids, "
            "blocked_action_ids, confidence, and rationale. Do not cite assertion ids that are not present. "
            "If no action is valid, return selected_action = null.\n",
            encoding="utf-8",
        )

    def write_governance_config(self) -> None:
        write_json(
            self.output_root / "config" / "trust_precedence.json",
            {"version": "trust-v1", "relations": TRUST_PRECEDENCE},
        )
        write_json(
            self.output_root / "config" / "source_catalog.json",
            {
                "version": "source-catalog-v1",
                "action_relevant_relations": TRUST_PRECEDENCE,
            },
        )
        write_json(self.output_root / "config" / "conflict_semantics.json", conflict_semantics())
        write_json(
            self.output_root / "config" / "action_registry.json",
            {
                "version": "action-registry-v1",
                "actions": [
                    {"action": "issue_refund", "kind": "effectful", "policy_family": "refund", "workflow_type": "refund_workflow"},
                    {"action": "request_manager_approval", "kind": "effectful", "policy_family": "refund", "workflow_type": "refund_workflow"},
                    {"action": "deny_refund", "kind": "effectful", "policy_family": "refund", "workflow_type": "refund_workflow"},
                    {"action": "reject_refund", "kind": "effectful", "policy_family": "refund", "workflow_type": "refund_workflow"},
                    {"action": "escalate_ticket", "kind": "effectful", "policy_family": "sla", "workflow_type": "support_escalation_workflow"},
                    {"action": "request_customer_info", "kind": "effectful", "policy_family": "sla", "workflow_type": "support_escalation_workflow"},
                    {"action": "resolve_ticket", "kind": "effectful", "policy_family": "sla", "workflow_type": "support_escalation_workflow"},
                ],
            },
        )

    def write_schemas(self) -> None:
        common_schema = {"type": "object", "additionalProperties": True}
        schemas = {
            "entities.schema.json": {
                "type": "object",
                "required": ["entity_id", "entity_type"],
                "additionalProperties": True,
            },
            "assertion_event.schema.json": {
                "type": "object",
                "required": [
                    "assertion_id",
                    "subject",
                    "predicate",
                    "object",
                    "assertion_type",
                    "entity_scope",
                    "relation_scope",
                    "event_time",
                    "record_time",
                    "valid_from",
                    "ontology_version",
                    "policy_version",
                    "source",
                    "lifecycle_state",
                ],
                "additionalProperties": True,
            },
            "task.schema.json": {
                "type": "object",
                "required": [
                    "task_id",
                    "task_type",
                    "natural_language_question",
                    "decision_time",
                    "entity_scope",
                    "target_ontology_version",
                    "target_policy_version",
                    "retrieval_mode",
                    "candidate_actions",
                    "assertion_templates",
                ],
                "additionalProperties": True,
            },
            "gold_label.schema.json": {
                "type": "object",
                "required": [
                    "task_id",
                    "answer_class",
                    "eligible_assertion_ids",
                    "expected_suppression",
                    "valid_actions",
                    "blocked_actions",
                    "acceptable_llm_outputs",
                    "stage_labels",
                ],
                "additionalProperties": True,
            },
            "context_packet.schema.json": {
                "type": "object",
                "required": [
                    "packet_id",
                    "task_id",
                    "split",
                    "method",
                    "feature_mask",
                    "retrieved_assertion_ids",
                    "retrieved_assertions",
                    "suppressed_assertion_ids",
                    "predicted_valid_actions",
                    "predicted_blocked_actions",
                    "suppression_reasons",
                    "suppression_reason_lists",
                    "action_support_by_action",
                    "blocked_action_reasons",
                    "bindings_consulted",
                    "unresolved_conflicts",
                    "conflict_trace",
                    "provenance_trace",
                    "audit_trace",
                    "snapshot_id",
                    "append_log_checkpoint",
                    "query_relevant_candidate_count",
                    "token_count_estimate",
                    "retrieval_latency_ms",
                    "initial_retrieved_assertion_ids",
                    "decision_evidence_assertion_ids",
                    "decision_evidence_status",
                    "initial_retrieval_budget",
                    "decision_evidence_count",
                ],
                "properties": {
                    "packet_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "split": {"type": "string"},
                    "method": {"type": "string"},
                    "feature_mask": {
                        "type": "object",
                        "required": [
                            "mask_version",
                            "oracle_fields_visible",
                            "gold_fields_visible",
                            "current_workflow_state_visible_to_llm",
                            "use_lifecycle_state",
                            "use_validity_interval",
                            "use_record_visibility",
                            "use_provenance_trust",
                            "use_provenance_activity",
                            "use_source_eligibility",
                            "use_ontology_versioning",
                            "use_policy_versioning",
                            "use_supersession_links",
                            "use_contradiction_resolver",
                            "use_conflict_trust",
                            "use_workflow_state_binding",
                            "use_workflow_instance_scope",
                            "use_action_target_binding",
                        ],
                        "properties": {
                            "mask_version": {"type": "string"},
                            "oracle_fields_visible": {"type": "boolean"},
                            "gold_fields_visible": {"type": "boolean"},
                            "current_workflow_state_visible_to_llm": {"type": "boolean"},
                            "use_lifecycle_state": {"type": "boolean"},
                            "use_validity_interval": {"type": "boolean"},
                            "use_record_visibility": {"type": "boolean"},
                            "use_provenance_trust": {"type": "boolean"},
                            "use_provenance_activity": {"type": "boolean"},
                            "use_source_eligibility": {"type": "boolean"},
                            "use_ontology_versioning": {"type": "boolean"},
                            "use_policy_versioning": {"type": "boolean"},
                            "use_supersession_links": {"type": "boolean"},
                            "use_contradiction_resolver": {"type": "boolean"},
                            "use_conflict_trust": {"type": "boolean"},
                            "use_workflow_state_binding": {"type": "boolean"},
                            "use_workflow_instance_scope": {"type": "boolean"},
                            "use_action_target_binding": {"type": "boolean"},
                        },
                        "additionalProperties": False,
                    },
                    "retrieved_assertion_ids": {"type": "array", "items": {"type": "string"}},
                    "initial_retrieved_assertion_ids": {"type": "array", "items": {"type": "string"}},
                    "decision_evidence_assertion_ids": {"type": "array", "items": {"type": "string"}},
                    "decision_evidence_status": {"type": "string"},
                    "initial_retrieval_budget": {"type": "integer"},
                    "decision_evidence_count": {"type": "integer"},
                    "retrieved_assertions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["assertion_id", "subject", "predicate", "object", "assertion_type", "event_time", "record_time"],
                            "properties": {
                                "assertion_id": {"type": "string"},
                                "subject": {"type": "string"},
                                "predicate": {"type": "string"},
                                "object": {"type": ["string", "number", "boolean", "null"]},
                                "assertion_type": {"type": "string"},
                                "event_time": {"type": "string"},
                                "record_time": {"type": "string"},
                                "entity_scope": {"type": "array", "items": {"type": "string"}},
                                "valid_from": {"type": "string"},
                                "valid_until": {"type": ["string", "null"]},
                                "ontology_version": {"type": "string"},
                                "policy_version": {"type": "string"},
                                "source": {"type": ["string", "null"]},
                                "trust_class": {"type": ["string", "null"]},
                                "provenance_activity": {"type": ["string", "null"]},
                                "lifecycle_state": {"type": "string"},
                                "supersedes": {"type": "array", "items": {"type": "string"}},
                                "superseded_by": {"type": "array", "items": {"type": "string"}},
                                "contradiction_group": {"type": ["string", "null"]},
                                "workflow_instance_id": {"type": ["string", "null"]},
                                "workflow_state_binding": {"type": ["string", "null"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "suppressed_assertion_ids": {"type": "array", "items": {"type": "string"}},
                    "suppression_reasons": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "suppression_reason_lists": {
                        "type": "object",
                        "additionalProperties": {"type": "array", "items": {"type": "string"}},
                    },
                    "predicted_valid_actions": {"type": "array", "items": {"type": "string"}},
                    "predicted_blocked_actions": {"type": "array", "items": {"type": "string"}},
                    "action_support_by_action": {
                        "type": "object",
                        "additionalProperties": {"type": "array", "items": {"type": "string"}},
                    },
                    "blocked_action_reasons": {
                        "type": "object",
                        "additionalProperties": {"type": "array", "items": {"type": "string"}},
                    },
                    "bindings_consulted": {"type": "object", "additionalProperties": {"type": "object"}},
                    "unresolved_conflicts": {"type": "array", "items": {"type": "object"}},
                    "conflict_trace": {"type": "array", "items": {"type": "object"}},
                    "provenance_trace": {"type": "array", "items": {"type": "object"}},
                    "audit_trace": {"type": "array", "items": {"type": "object"}},
                    "snapshot_id": {"type": "string"},
                    "append_log_checkpoint": {"type": "integer"},
                    "query_relevant_candidate_count": {"type": "integer"},
                    "token_count_estimate": {"type": "integer"},
                    "retrieval_latency_ms": {"type": "number"},
                },
                "additionalProperties": False,
            },
            "llm_output.schema.json": {
                "type": "object",
                "required": [
                    "task_id",
                    "method",
                    "answer",
                    "selected_action",
                    "support_assertion_ids",
                    "blocked_action_ids",
                    "confidence",
                    "rationale",
                ],
                "properties": {
                    "task_id": {"type": "string"},
                    "method": {"type": "string"},
                    "answer": {"type": "string"},
                    "selected_action": {"type": ["string", "null"]},
                    "support_assertion_ids": {"type": "array", "items": {"type": "string"}},
                    "blocked_action_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": ["number", "string"]},
                    "rationale": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
        for name, schema in schemas.items():
            write_json(self.output_root / "schema" / name, schema)

    def write_ontologies(self) -> None:
        write_json(
            self.output_root / "ontology" / "ontology_v1.json",
            {"version": "ov_1", "relations": ["support_plan", "subscription_status", "owner", "severity", "refund_status"]},
        )
        write_json(
            self.output_root / "ontology" / "ontology_v2.json",
            {"version": "ov_2", "relations": ["entitlement_profile", "sla_profile", "subscription_status", "owner", "workflow_state"]},
        )
        write_json(
            self.output_root / "ontology" / "ontology_v3.json",
            {
                "version": "ov_3",
                "relations": [
                    "product_entitlement",
                    "support_entitlement",
                    "contractual_entitlement",
                    "sla_profile",
                    "workflow_state",
                    "subscription_status",
                    "account_owner",
                ],
            },
        )
        write_json(
            self.output_root / "ontology" / "ontology_mappings.json",
            {
                "mappings": [
                    {"from_ov": "ov_1", "to_ov": "ov_2", "from_relation": "support_plan", "to_relation": "entitlement_profile", "map_type": "rewrite"},
                    {"from_ov": "ov_1", "to_ov": "ov_2", "from_relation": "support_plan", "to_relation": "sla_profile", "map_type": "split"},
                    {"from_ov": "ov_1", "to_ov": "ov_2", "from_relation": "refund_status", "to_relation": "workflow_state", "map_type": "rewrite"},
                    {"from_ov": "ov_2", "to_ov": "ov_3", "from_relation": "entitlement_profile", "to_relation": "product_entitlement", "map_type": "split"},
                    {"from_ov": "ov_2", "to_ov": "ov_3", "from_relation": "entitlement_profile", "to_relation": "support_entitlement", "map_type": "split"},
                    {"from_ov": "ov_2", "to_ov": "ov_3", "from_relation": "entitlement_profile", "to_relation": "contractual_entitlement", "map_type": "split"},
                    {"from_ov": "ov_2", "to_ov": "ov_3", "from_relation": "sla_profile", "to_relation": "sla_profile", "map_type": "identity"},
                    {"from_ov": "ov_2", "to_ov": "ov_3", "from_relation": "workflow_state", "to_relation": "workflow_state", "map_type": "identity"},
                ]
            },
        )

    def write_policies(self) -> None:
        policies = {
            "refund_policy_v1.json": [
                {"policy_version": "refund_policy_v1", "policy_family": "refund", "action": "issue_refund", "permit_or_deny": "permit", "priority": 10, "guard": {"and": [{"equals": ["support_entitlement", "EnterprisePlus"]}, {"in": ["refund_amount", ["low", "medium"]]}]}},
                {"policy_version": "refund_policy_v1", "policy_family": "refund", "action": "request_manager_approval", "permit_or_deny": "permit", "priority": 5, "guard": {"equals": ["support_entitlement", "Basic"]}},
            ],
            "refund_policy_v2.json": [
                {"policy_version": "refund_policy_v2", "policy_family": "refund", "action": "issue_refund", "permit_or_deny": "permit", "priority": 10, "guard": {"and": [{"equals": ["workflow_state", "approved"]}, {"not_equals": ["subscription_status", "suspended"]}]}},
                {"policy_version": "refund_policy_v2", "policy_family": "refund", "action": "request_manager_approval", "permit_or_deny": "permit", "priority": 8, "guard": {"equals": ["workflow_state", "eligibility_checked"]}},
                {"policy_version": "refund_policy_v2", "policy_family": "refund", "action": "deny_refund", "permit_or_deny": "permit", "priority": 7, "guard": {"in": ["workflow_state", ["eligibility_checked", "manager_review"]] }},
                {"policy_version": "refund_policy_v2", "policy_family": "refund", "action": "reject_refund", "permit_or_deny": "permit", "priority": 7, "guard": {"equals": ["workflow_state", "manager_review"]}},
            ],
            "sla_policy_v1.json": [
                {"policy_version": "sla_policy_v1", "policy_family": "sla", "action": "escalate_ticket", "permit_or_deny": "permit", "priority": 10, "guard": {"and": [{"equals": ["ticket_severity", "critical"]}, {"lte_hours_open": 2}, {"equals": ["support_entitlement", "EnterprisePlus"]}]}},
            ],
            "sla_policy_v2.json": [
                {"policy_version": "sla_policy_v2", "policy_family": "sla", "action": "escalate_ticket", "permit_or_deny": "permit", "priority": 10, "guard": {"and": [{"equals": ["ticket_severity", "critical"]}, {"in": ["support_entitlement", ["Premium", "EnterprisePlus"]]}]}},
                {"policy_version": "sla_policy_v2", "policy_family": "sla", "action": "request_customer_info", "permit_or_deny": "permit", "priority": 5, "guard": {"equals": ["workflow_state", "triaged"]}},
                {"policy_version": "sla_policy_v2", "policy_family": "sla", "action": "resolve_ticket", "permit_or_deny": "permit", "priority": 5, "guard": {"equals": ["workflow_state", "escalated"]}},
            ],
        }
        for name, rules in policies.items():
            write_json(self.output_root / "policy" / name, {"rules": rules})

    def write_workflows(self) -> None:
        write_json(
            self.output_root / "workflows" / "refund_workflow.json",
            {
                "workflow_type": "refund_workflow",
                "states": ["submitted", "eligibility_checked", "manager_review_pending", "manager_review", "approved", "rejected", "refund_issued", "closed", "appeal_opened"],
                "transitions": [
                    {"from": "submitted", "action": "check_eligibility", "to": "eligibility_checked", "guard": {"exists": "refund_request"}},
                    {"from": "eligibility_checked", "action": "request_manager_approval", "to": "manager_review_pending", "guard": {"equals": ["workflow_state", "eligibility_checked"]}},
                    {"from": "eligibility_checked", "action": "deny_refund", "to": "rejected", "guard": {"equals": ["workflow_state", "eligibility_checked"]}},
                    {"from": "manager_review_pending", "action": "start_manager_review", "to": "manager_review", "guard": {"equals": ["workflow_state", "manager_review_pending"]}},
                    {"from": "manager_review", "action": "approve_refund", "to": "approved", "guard": {"equals": ["workflow_state", "manager_review"]}},
                    {"from": "manager_review", "action": "reject_refund", "to": "rejected", "guard": {"equals": ["workflow_state", "manager_review"]}},
                    {"from": "approved", "action": "issue_refund", "to": "refund_issued", "guard": {"equals": ["workflow_state", "approved"]}},
                    {"from": "rejected", "action": "close_case", "to": "closed", "guard": {"equals": ["workflow_state", "rejected"]}},
                    {"from": "refund_issued", "action": "close_case", "to": "closed", "guard": {"equals": ["workflow_state", "refund_issued"]}},
                    {"from": "closed", "action": "open_appeal", "to": "appeal_opened", "guard": {"equals": ["workflow_state", "closed"]}},
                ],
            },
        )
        write_json(
            self.output_root / "workflows" / "support_escalation_workflow.json",
            {
                "workflow_type": "support_escalation_workflow",
                "states": ["opened", "triaged", "waiting_on_customer", "escalated", "resolved", "closed", "reopened"],
                "transitions": [
                    {"from": "opened", "action": "triage_ticket", "to": "triaged", "guard": {"equals": ["workflow_state", "opened"]}},
                    {"from": "triaged", "action": "request_customer_info", "to": "waiting_on_customer", "guard": {"equals": ["workflow_state", "triaged"]}},
                    {"from": "triaged", "action": "escalate_ticket", "to": "escalated", "guard": {"equals": ["workflow_state", "triaged"]}},
                    {"from": "waiting_on_customer", "action": "receive_customer_info", "to": "triaged", "guard": {"equals": ["workflow_state", "waiting_on_customer"]}},
                    {"from": "escalated", "action": "resolve_ticket", "to": "resolved", "guard": {"equals": ["workflow_state", "escalated"]}},
                    {"from": "resolved", "action": "close_ticket", "to": "closed", "guard": {"equals": ["workflow_state", "resolved"]}},
                    {"from": "closed", "action": "reopen_ticket", "to": "reopened", "guard": {"equals": ["workflow_state", "closed"]}},
                ],
            },
        )

    def generate_entities(self) -> None:
        for i in range(1, 41):
            self.add_entity("Customer", nid("cust", i), region=REGIONS[i % len(REGIONS)])
        for i in range(1, 36):
            self.add_entity("Account", nid("acct", i), region=REGIONS[i % len(REGIONS)])
        for i in range(1, 11):
            self.add_entity("Household", nid("hh", i))
        for i in range(1, 36):
            self.add_entity("Subscription", nid("sub", i))
        for i in range(1, 61):
            self.add_entity("ProductEntitlement", nid("pent", i), level=PLAN_VALUES[i % len(PLAN_VALUES)])
        for i in range(1, 61):
            self.add_entity("SupportEntitlement", nid("sent", i), level=PLAN_VALUES[i % len(PLAN_VALUES)])
        for i in range(1, 31):
            self.add_entity("ContractualEntitlement", nid("cent", i), tier=PLAN_VALUES[i % len(PLAN_VALUES)])
        for i in range(1, 21):
            self.add_entity("SLAProfile", nid("sla", i), tier=PLAN_VALUES[i % len(PLAN_VALUES)])
        for i in range(1, 81):
            self.add_entity("SupportTicket", nid("ticket", i), severity=SEVERITIES[i % len(SEVERITIES)])
        for i in range(1, 26):
            self.add_entity("Incident", nid("inc", i))
        for i in range(1, 41):
            self.add_entity("RefundRequest", nid("refund", i), amount_band=AMOUNT_BANDS[i % len(AMOUNT_BANDS)])
        for i in range(1, 121):
            workflow_type = "refund_workflow" if i <= 40 else "support_escalation_workflow"
            self.add_entity("WorkflowCase", nid("case", i), workflow_type=workflow_type)
        for i in range(1, 9):
            self.add_entity("Policy", nid("policy", i), family="refund" if i <= 4 else "sla")
        for i, region in enumerate(REGIONS, 1):
            self.add_entity("Region", f"region_{region}", code=region)
        for i in range(1, 21):
            self.add_entity("AccountOwner", nid("owner", i))
        for i in range(1, 9):
            self.add_entity("Product", nid("prod", i))
        for value in PLAN_VALUES:
            self.add_entity("EntitlementProfile", f"profile_{value}", value=value)

    def generate_account_timelines(self) -> None:
        for idx, acct in enumerate(self.entity_ids["Account"], 1):
            current_plan = PLAN_VALUES[idx % len(PLAN_VALUES)]
            old_plan = PLAN_VALUES[(idx + 1) % len(PLAN_VALUES)]
            status = STATUSES[0 if idx % 7 else 1]
            old_owner = self.entity_ids["AccountOwner"][(idx + 3) % len(self.entity_ids["AccountOwner"])]
            owner = self.entity_ids["AccountOwner"][idx % len(self.entity_ids["AccountOwner"])]
            refund_case = self.entity_ids["WorkflowCase"][idx - 1 if idx <= 35 else 0]
            ticket_case = self.entity_ids["WorkflowCase"][40 + ((idx - 1) % 80)]
            refund_state = ["submitted", "eligibility_checked", "manager_review_pending", "manager_review", "approved", "rejected"][idx % 6]
            ticket_state = ["opened", "triaged", "waiting_on_customer", "escalated", "resolved"][idx % 5]
            ticket = self.entity_ids["SupportTicket"][(idx - 1) % 80]
            refund = self.entity_ids["RefundRequest"][(idx - 1) % 40]
            severity = SEVERITIES[idx % len(SEVERITIES)]
            amount = AMOUNT_BANDS[idx % len(AMOUNT_BANDS)]
            t_old = BASE_TIME + timedelta(days=idx % 20)
            t_change = BASE_TIME + timedelta(days=35 + (idx % 20))
            t_current = BASE_TIME + timedelta(days=45 + (idx % 10))

            self.add_state_change("Subscription upgrade/downgrade", acct, old_plan, current_plan, t_change)
            self.add_state_change("Subscription suspension/reactivation", acct, "active", status, t_current + timedelta(hours=idx))
            self.add_state_change("Account owner change", acct, old_owner, owner, t_change + timedelta(hours=idx))
            if idx <= 20:
                self.add_state_change("Refund workflow transition", refund_case, "submitted", refund_state, t_current)
            if idx <= 15:
                self.add_state_change("Ticket escalation transition", ticket_case, "opened", ticket_state, t_current)

            old_a = self.add_assertion(
                subject=acct,
                predicate="support_plan",
                obj=old_plan,
                assertion_type="semantic_fact",
                event_time=t_old,
                record_time=DECISION_TIME - timedelta(days=idx % 7, hours=idx),
                valid_from=t_old,
                valid_until=None,
                ontology_version="ov_2",
                policy_version="refund_policy_v1",
                source="billing",
                lifecycle_state="superseded",
                canonical_role="stale",
            )
            cur_ent = self.add_assertion(
                subject=acct,
                predicate="support_entitlement",
                obj=current_plan,
                assertion_type="semantic_fact",
                event_time=t_change,
                valid_from=t_change,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source="billing",
                lifecycle_state="active",
                supersedes=[old_a],
                canonical_role="current",
            )
            delayed_stale = self.add_assertion(
                subject=acct,
                predicate="support_entitlement",
                obj=old_plan,
                assertion_type="semantic_fact",
                event_time=t_old + timedelta(hours=1),
                record_time=DECISION_TIME - timedelta(days=idx % 5, minutes=idx),
                valid_from=t_old,
                valid_until=None,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source="support_note",
                lifecycle_state="superseded",
                superseded_by=[cur_ent],
                canonical_role="stale",
            )
            self.assertion_by_id(cur_ent)["supersedes"].append(delayed_stale)
            # Backpatch superseded_by for old assertion.
            self.assertion_by_id(old_a)["superseded_by"] = [cur_ent]
            status_a = self.add_assertion(subject=acct, predicate="subscription_status", obj=status, event_time=t_current, valid_from=t_current, ontology_version="ov_3", policy_version="refund_policy_v2", source="billing")
            owner_a = self.add_assertion(subject=acct, predicate="account_owner", obj=owner, event_time=t_current, valid_from=t_current, ontology_version="ov_3", policy_version="refund_policy_v2", source="crm")
            sla_a = self.add_assertion(subject=acct, predicate="sla_profile", obj=current_plan, event_time=t_change, valid_from=t_change, ontology_version="ov_3", policy_version="sla_policy_v2", source="billing")
            prod_a = self.add_assertion(subject=acct, predicate="product_entitlement", obj=f"prod_{((idx - 1) % 8) + 1:03d}", event_time=t_change, valid_from=t_change, ontology_version="ov_3", policy_version="refund_policy_v2", source="billing")
            cont_a = self.add_assertion(subject=acct, predicate="contractual_entitlement", obj=current_plan, event_time=t_change, valid_from=t_change, ontology_version="ov_3", policy_version="refund_policy_v2", source="billing")
            refund_state_a = self.add_assertion(
                subject=refund_case,
                predicate="workflow_state",
                obj=refund_state,
                assertion_type="workflow_fact",
                entity_scope=[acct, refund_case],
                event_time=t_current,
                valid_from=t_current,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source="workflow_log",
                workflow_instance_id=refund_case,
                workflow_state_binding=refund_state,
            )
            ticket_state_a = self.add_assertion(
                subject=ticket_case,
                predicate="workflow_state",
                obj=ticket_state,
                assertion_type="workflow_fact",
                entity_scope=[acct, ticket_case],
                event_time=t_current,
                valid_from=t_current,
                ontology_version="ov_3",
                policy_version="sla_policy_v2",
                source="workflow_log",
                workflow_instance_id=ticket_case,
                workflow_state_binding=ticket_state,
            )
            ticket_sev_a = self.add_assertion(
                subject=ticket,
                predicate="ticket_severity",
                obj=severity,
                entity_scope=[acct, ticket],
                event_time=t_current,
                valid_from=t_current,
                ontology_version="ov_3",
                policy_version="sla_policy_v2",
                source="workflow_log",
            )
            amount_a = self.add_assertion(
                subject=refund,
                predicate="refund_amount",
                obj=amount,
                entity_scope=[acct, refund],
                event_time=t_current,
                valid_from=t_current,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source="billing",
            )

            self.account[acct] = {
                "current_plan": current_plan,
                "old_plan": old_plan,
                "status": status,
                "owner": owner,
                "refund_case": refund_case,
                "refund": refund,
                "refund_state": refund_state,
                "ticket_case": ticket_case,
                "ticket": ticket,
                "ticket_state": ticket_state,
                "severity": severity,
                "amount": amount,
                "current_assertions": [cur_ent, status_a, owner_a, sla_a, prod_a, cont_a, refund_state_a, ticket_state_a, ticket_sev_a, amount_a],
                "stale_assertions": [old_a, delayed_stale],
                "support_entitlement_assertion": cur_ent,
                "status_assertion": status_a,
                "owner_assertion": owner_a,
                "sla_assertion": sla_a,
                "refund_state_assertion": refund_state_a,
                "ticket_state_assertion": ticket_state_a,
                "ticket_severity_assertion": ticket_sev_a,
                "refund_amount_assertion": amount_a,
                "contradiction_groups": [],
                "contradiction_losers": [],
                "contradiction_winners": [],
            }

    def generate_policy_assertions(self) -> None:
        for pv, source in [
            ("refund_policy_v1", "policy_registry"),
            ("refund_policy_v2", "policy_registry"),
            ("sla_policy_v1", "policy_registry"),
            ("sla_policy_v2", "policy_registry"),
        ]:
            for i in range(15):
                pred = "refund_rule" if pv.startswith("refund") else "sla_rule"
                obj = f"{pv}_rule_{i:02d}"
                state = "superseded" if pv.endswith("v1") and i < 8 else "active"
                valid_until = BASE_TIME + timedelta(days=50) if state == "superseded" else None
                self.add_assertion(
                    subject=pv,
                    predicate=pred,
                    obj=obj,
                    assertion_type="policy_fact",
                    event_time=BASE_TIME + timedelta(days=i),
                    valid_from=BASE_TIME + timedelta(days=i),
                    valid_until=valid_until,
                    ontology_version="ov_3" if pv.endswith("v2") else "ov_2",
                    policy_version=pv,
                    source=source,
                    lifecycle_state=state,
                    canonical_role="policy",
                )
        self.add_state_change("SLA policy change", "sla_policy", "sla_policy_v1", "sla_policy_v2", BASE_TIME + timedelta(days=50))
        self.add_state_change("Refund policy change", "refund_policy", "refund_policy_v1", "refund_policy_v2", BASE_TIME + timedelta(days=50))
        for i in range(9):
            self.add_state_change("SLA policy change", f"sla_policy_rule_{i}", "v1", "v2", BASE_TIME + timedelta(days=51 + i))
            self.add_state_change("Refund policy change", f"refund_policy_rule_{i}", "v1", "v2", BASE_TIME + timedelta(days=51 + i))
        for i in range(5):
            self.add_state_change("Ontology migration event", f"ontology_migration_{i}", "ov_2", "ov_3", BASE_TIME + timedelta(days=45 + i))

    def generate_additional_state_changes(self) -> None:
        families = [
            ("Entitlement grant/revoke/change", 25),
            ("Household/account relationship change", 10),
            ("Account merge", 8),
            ("Account split", 7),
        ]
        accounts = self.entity_ids["Account"]
        for fam, count in families:
            for i in range(count):
                acct = accounts[(i + len(self.state_changes)) % len(accounts)]
                self.add_state_change(fam, acct, f"before_{i}", f"after_{i}", BASE_TIME + timedelta(days=20 + i))

    def inject_contradictions(self) -> None:
        relation_cycle = [
            ("subscription_status", "active", "suspended", "billing", "crm"),
            ("support_entitlement", "Premium", "Basic", "billing", "support_note"),
            ("account_owner", "owner_001", "owner_002", "crm", "support_note"),
            ("refund_rule", "manager_review_required", "immediate_refund_allowed", "policy_registry", "generated_summary"),
            ("workflow_state", "eligibility_checked", "approved", "workflow_log", "support_note"),
            ("sla_profile", "Premium", "Standard", "billing", "generated_summary"),
            ("product_entitlement", "prod_001", "prod_002", "billing", "generated_summary"),
        ]
        accounts = self.entity_ids["Account"]
        for i in range(60):
            relation, win_obj, lose_obj, win_source, lose_source = relation_cycle[i % len(relation_cycle)]
            acct = accounts[i % len(accounts)]
            subject = self.account[acct]["refund_case"] if relation == "workflow_state" else acct
            cg = f"cg_{self.contradiction_counter:04d}"
            self.contradiction_counter += 1
            event_time = BASE_TIME + timedelta(days=52 + (i % 20), hours=i)
            winner = self.add_assertion(
                subject=subject,
                predicate=relation,
                obj=win_obj,
                assertion_type="workflow_fact" if relation == "workflow_state" else ("policy_fact" if relation == "refund_rule" else "semantic_fact"),
                entity_scope=[acct, subject] if relation == "workflow_state" else [acct],
                event_time=event_time,
                valid_from=event_time,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source=win_source,
                lifecycle_state="active",
                contradiction_group=cg,
                workflow_instance_id=subject if relation == "workflow_state" else None,
                workflow_state_binding=win_obj if relation == "workflow_state" else None,
                canonical_role="contradiction_winner",
            )
            loser = self.add_assertion(
                subject=subject,
                predicate=relation,
                obj=lose_obj,
                assertion_type="workflow_fact" if relation == "workflow_state" else ("policy_fact" if relation == "refund_rule" else "semantic_fact"),
                entity_scope=[acct, subject] if relation == "workflow_state" else [acct],
                event_time=event_time + timedelta(minutes=2),
                valid_from=event_time,
                ontology_version="ov_3",
                policy_version="refund_policy_v2",
                source=lose_source,
                lifecycle_state="active",
                contradiction_group=cg,
                workflow_instance_id=subject if relation == "workflow_state" else None,
                workflow_state_binding=lose_obj if relation == "workflow_state" else None,
                canonical_role="contradiction_loser",
            )
            group = {
                "contradiction_group_id": cg,
                "conflict_key": [subject, relation, iso(DECISION_TIME)],
                "assertion_ids": [winner, loser],
                "winner_assertion_id": winner,
                "loser_assertion_ids": [loser],
                "unresolved": False,
                "trust_precedence_rationale": f"{win_source} outranks {lose_source} for {relation}",
                "safe_fallback_required": False,
            }
            self.contradiction_groups.append(group)
            self.account[acct]["contradiction_groups"].append(cg)
            self.account[acct]["contradiction_winners"].append(winner)
            self.account[acct]["contradiction_losers"].append(loser)

    def generate_missing_provenance(self) -> None:
        for i, acct in enumerate(self.entity_ids["Account"], 1):
            if i % 3 == 0:
                aid = self.add_assertion(
                    subject=acct,
                    predicate="support_entitlement",
                    obj="EnterprisePlus",
                    event_time=BASE_TIME + timedelta(days=55, hours=i),
                    valid_from=BASE_TIME + timedelta(days=55),
                    ontology_version="ov_3",
                    policy_version="refund_policy_v2",
                    source="none",
                    lifecycle_state="active",
                    canonical_role="missing_provenance",
                )
                self.account[acct].setdefault("missing_provenance_assertions", []).append(aid)

    def refund_candidates_for_state(self, state: str) -> list[str]:
        if state == "manager_review":
            return ["issue_refund", "request_manager_approval", "reject_refund"]
        return ["issue_refund", "request_manager_approval", "deny_refund"]

    def valid_refund_actions(self, state: str, status: str) -> tuple[list[str], list[str]]:
        candidates = self.refund_candidates_for_state(state)
        if state == "approved":
            valid = [] if status == "suspended" else ["issue_refund"]
            return valid, [a for a in candidates if a not in set(valid)]
        if state == "eligibility_checked":
            return ["request_manager_approval", "deny_refund"], ["issue_refund"]
        if state == "manager_review":
            return ["reject_refund"], ["issue_refund", "request_manager_approval"]
        return [], candidates

    def valid_ticket_actions(self, state: str, severity: str, plan: str) -> tuple[list[str], list[str]]:
        candidates = ["escalate_ticket", "request_customer_info", "resolve_ticket"]
        if state == "triaged" and severity == "critical" and plan in {"Premium", "EnterprisePlus"}:
            return ["escalate_ticket", "request_customer_info"], ["resolve_ticket"]
        if state == "triaged":
            return ["request_customer_info"], ["escalate_ticket", "resolve_ticket"]
        if state == "escalated":
            return ["resolve_ticket"], ["escalate_ticket", "request_customer_info"]
        return [], candidates

    def add_task(self, task_type: str, acct: str, question: str, relation_scope, candidate_actions=None, audit_time=None) -> None:
        rec = self.account[acct]
        tid = f"t_{self.task_counter:05d}"
        self.task_counter += 1
        candidate_actions = candidate_actions or []
        workflow_instance = None
        workflow_state = None
        if "refund" in task_type or task_type == "workflow_state_next_action":
            workflow_instance = rec["refund_case"]
            workflow_state = rec["refund_state"]
        elif "sla" in task_type:
            workflow_instance = rec["ticket_case"]
            workflow_state = rec["ticket_state"]
        task = {
            "task_id": tid,
            "task_type": task_type,
            "natural_language_question": question,
            "decision_time": iso(DECISION_TIME),
            "entity_scope": self.task_entity_scope(task_type, acct),
            "entity_scope_mode": "graph_expanded" if task_type in {"policy_valid_refund_action", "workflow_state_next_action", "sla_valid_escalation_action"} else "exact",
            "relation_scope": relation_scope,
            "target_ontology_version": "ov_3",
            "target_policy_version": "sla_policy_v2" if "sla" in task_type else "refund_policy_v2",
            "trust_table_version": "trust-v1",
            "workflow_instance_id": workflow_instance,
            "current_workflow_state": workflow_state,
            "audit_time": iso(audit_time) if audit_time else None,
            "disallowed_sources": [],
            "retrieval_mode": "audit_historical" if task_type == "audit_valid_historical_explanation" else "current_action",
            "candidate_actions": candidate_actions,
            "assertion_templates": relation_scope,
        }
        self.tasks.append(task)
        self.gold.append(self.make_gold(task, acct))

    def task_entity_scope(self, task_type: str, acct: str) -> list[str]:
        rec = self.account[acct]
        scope = [acct]
        if task_type in {"policy_valid_refund_action", "workflow_state_next_action"}:
            scope.extend([rec["refund_case"], rec["refund"]])
        elif task_type == "sla_valid_escalation_action":
            scope.extend([rec["ticket_case"], rec["ticket"]])
        return scope

    def make_gold(self, task, acct: str):
        rec = self.account[acct]
        eligible = []
        stale = list(rec["stale_assertions"])
        suppression = {}
        for sid in stale:
            reasons = ["superseded_by_newer_assertion"]
            if self.assertion_by_id(sid).get("valid_until"):
                reasons.insert(0, "not_valid_at_decision_time")
            suppression[sid] = reasons
        for sid in rec.get("missing_provenance_assertions", []):
            suppression[sid] = ["missing_provenance"]
        for sid in rec["contradiction_losers"][:2]:
            suppression[sid] = ["contradiction_loser"]
        if task["task_type"] == "current_factual_recall":
            entitlement_candidates = [rec["support_entitlement_assertion"]] + [
                assertion_id
                for assertion_id in rec["contradiction_winners"]
                if self.assertion_by_id(assertion_id)["predicate"] == "support_entitlement"
                and (self.assertion_by_id(assertion_id).get("record_time") or "")
                <= task["decision_time"]
            ]
            winners = resolve_declared_conflict(
                entitlement_candidates,
                {row["assertion_id"]: row for row in self.assertions},
                "support_entitlement",
                task["decision_time"],
            )
            eligible = winners
            answer_class = self.assertion_by_id(winners[0])["object"] if winners else "unresolved"
            valid_actions, blocked_actions = [], []
        elif task["task_type"] == "relationship_aware_retrieval":
            # Freeze the owner that the declared conflict contract selects, not
            # the account's earlier construction-time pointer.  Injected
            # contradictions can contain a newer assertion from the same
            # highest-authority source; descending record time then makes that
            # assertion the current owner under the released resolver.
            owner_candidates = [rec["owner_assertion"]] + [
                assertion_id
                for assertion_id in rec["contradiction_winners"]
                if self.assertion_by_id(assertion_id)["predicate"] == "account_owner"
                and (self.assertion_by_id(assertion_id).get("record_time") or "")
                <= task["decision_time"]
            ]
            winners = resolve_declared_conflict(
                owner_candidates,
                {row["assertion_id"]: row for row in self.assertions},
                "account_owner",
                task["decision_time"],
            )
            eligible = winners
            answer_class = self.assertion_by_id(winners[0])["object"] if winners else "unresolved"
            valid_actions, blocked_actions = [], []
        elif task["task_type"] == "policy_valid_refund_action":
            eligible = [rec["support_entitlement_assertion"], rec["status_assertion"], rec["refund_state_assertion"]]
            valid_actions, blocked_actions = self.valid_refund_actions(rec["refund_state"], rec["status"])
            answer_class = "valid_action_available" if valid_actions else "all_actions_blocked"
        elif task["task_type"] == "sla_valid_escalation_action":
            eligible = [rec["support_entitlement_assertion"], rec["ticket_state_assertion"], rec["ticket_severity_assertion"], rec["sla_assertion"]]
            valid_actions, blocked_actions = self.valid_ticket_actions(rec["ticket_state"], rec["severity"], rec["current_plan"])
            answer_class = "valid_action_available" if valid_actions else "all_actions_blocked"
        elif task["task_type"] == "workflow_state_next_action":
            eligible = [rec["refund_state_assertion"], rec["status_assertion"]]
            valid_actions, blocked_actions = self.valid_refund_actions(rec["refund_state"], rec["status"])
            answer_class = rec["refund_state"]
        elif task["task_type"] == "contradiction_handling":
            eligible = rec["contradiction_winners"][:1] or [rec["support_entitlement_assertion"]]
            valid_actions, blocked_actions = [], []
            answer_class = "unique_winner"
        else:
            eligible = rec["stale_assertions"][:1] + [rec["support_entitlement_assertion"]]
            valid_actions, blocked_actions = [], []
            answer_class = "historical_explanation"
        support_sets = [eligible] if eligible else [[]]
        return {
            "task_id": task["task_id"],
            "answer_class": answer_class,
            "correct_answer": f"{answer_class} for {acct}",
            "eligible_assertion_ids": eligible,
            "assertion_eligible_ids": eligible,
            "resolved_eligible_assertion_ids": eligible,
            "packet_eligible_assertion_ids": eligible,
            "stale_or_superseded_assertion_ids": stale,
            "contradiction_group_ids": rec["contradiction_groups"][:2],
            "contradiction_winner_ids": rec["contradiction_winners"][:2],
            "unresolved_contradiction_ids": [],
            "valid_actions": valid_actions,
            "blocked_actions": blocked_actions,
            "action_support_by_action": {a: eligible for a in valid_actions},
            "provenance_support": {aid: [self.source_of(aid)] for aid in eligible},
            "ontology_version_compatibility": {"compatible": eligible, "migrated": stale[:1], "incompatible": []},
            "policy_version_compatibility": {
                "compatible_policy_assertions": [aid for aid in eligible if self.assertion_by_id(aid)["assertion_type"] == "policy_fact"],
                "incompatible_policy_assertions": [],
            },
            "workflow_state_compatibility": {
                "current_state": task["current_workflow_state"],
                "valid_transitions": valid_actions,
                "blocked_transitions": blocked_actions,
            },
            "expected_suppression": suppression,
            "acceptable_llm_outputs": {
                "selected_action": valid_actions + ([None] if not valid_actions else []),
                "must_not_select": blocked_actions,
                "required_support_sets": support_sets,
                "support_scoring_rule": "one_complete_set_required",
                "blocked_action_ids_must_include": blocked_actions,
            },
            "stage_labels": {
                "AssertionEligible": eligible,
                "B_q": eligible,
                "ActionAllowed": valid_actions,
                "ActionSupportEligible": {a: eligible for a in valid_actions},
                "PacketEligible": eligible,
            },
        }

    def assertion_by_id(self, aid: str):
        for row in self.assertions:
            if row["assertion_id"] == aid:
                return row
        raise KeyError(aid)

    def source_of(self, aid: str):
        return self.assertion_by_id(aid).get("source")

    def generate_tasks(self) -> None:
        accounts = self.entity_ids["Account"]
        task_specs = [
            ("current_factual_recall", "What is the current support entitlement?", ["support_entitlement"], []),
            ("relationship_aware_retrieval", "Who is the current account owner?", ["account_owner"], []),
            ("policy_valid_refund_action", "Can this account receive an immediate refund now?", ["support_entitlement", "subscription_status", "workflow_state"], None),
            ("sla_valid_escalation_action", "Should this support ticket be escalated now?", ["support_entitlement", "ticket_severity", "workflow_state", "sla_profile"], ["escalate_ticket", "request_customer_info", "resolve_ticket"]),
            ("workflow_state_next_action", "What is the next allowed refund workflow action?", ["workflow_state", "subscription_status"], None),
            ("contradiction_handling", "Which conflicting assertion should be trusted?", ["subscription_status", "support_entitlement", "workflow_state"], []),
            ("audit_valid_historical_explanation", "Why was the prior support plan changed?", ["support_plan", "support_entitlement"], []),
        ]
        for task_type, question, relations, actions in task_specs:
            for i in range(20):
                acct = accounts[(i + self.task_counter) % len(accounts)]
                actual_actions = actions
                if task_type in {"policy_valid_refund_action", "workflow_state_next_action"}:
                    actual_actions = self.refund_candidates_for_state(self.account[acct]["refund_state"])
                self.add_task(task_type, acct, question, relations, actual_actions, audit_time=BASE_TIME + timedelta(days=20))

    def split_and_write(self) -> None:
        rng = random.Random(self.seeds["seed_splits"])
        all_types = sorted({t["task_type"] for t in self.tasks})
        smoke_ordered = []
        used = set()
        for task_type in all_types:
            for i, task in enumerate(self.tasks):
                if i not in used and task["task_type"] == task_type:
                    smoke_ordered.append(i)
                    used.add(i)
                    break
        remaining = [i for i in range(len(self.tasks)) if i not in used]
        rng.shuffle(remaining)
        smoke_extra = remaining[: max(0, 10 - len(smoke_ordered))]
        smoke_i = set(smoke_ordered + smoke_extra)
        remaining = [i for i in range(len(self.tasks)) if i not in smoke_i]
        rng.shuffle(remaining)
        dev_i = set(remaining[:30])
        test_i = set(remaining[30:130])
        splits = {
            "smoke": ([self.tasks[i] for i in range(len(self.tasks)) if i in smoke_i], [self.gold[i] for i in range(len(self.gold)) if i in smoke_i]),
            "dev": ([self.tasks[i] for i in range(len(self.tasks)) if i in dev_i], [self.gold[i] for i in range(len(self.gold)) if i in dev_i]),
            "test": ([self.tasks[i] for i in range(len(self.tasks)) if i in test_i], [self.gold[i] for i in range(len(self.gold)) if i in test_i]),
        }
        for split, (tasks, gold) in splits.items():
            write_jsonl(self.output_root / "generated" / f"tasks_{split}.jsonl", tasks)
            write_jsonl(self.output_root / "generated" / f"gold_{split}.jsonl", gold)
        write_jsonl(self.output_root / "generated" / "entities.jsonl", self.entities)
        write_jsonl(self.output_root / "generated" / "canonical_state_timeline.jsonl", self.canonical)
        write_jsonl(self.output_root / "generated" / "state_changes.jsonl", self.state_changes)
        write_jsonl(self.output_root / "generated" / "assertion_events.jsonl", self.assertions)
        write_jsonl(self.output_root / "generated" / "contradiction_groups.jsonl", self.contradiction_groups)

    def write_readme(self) -> None:
        (self.output_root / "README.md").write_text(
            "# EvoMem-Enterprise Phase 2 Benchmark\n\n"
            "Generated by `scripts/generate_evomem_enterprise.py` with fixed seeds. "
            "Gold labels are created from canonical state timelines plus the injected-noise ledger, not from LGR output.\n\n"
            "Regenerate:\n\n"
            "```bash\npython3 scripts/generate_evomem_enterprise.py\npython3 scripts/validate_evomem_enterprise.py\n```\n",
            encoding="utf-8",
        )

    def run(self) -> None:
        self.build_static_artifacts()
        self.generate_entities()
        self.generate_account_timelines()
        self.generate_policy_assertions()
        self.generate_additional_state_changes()
        self.inject_contradictions()
        self.generate_missing_provenance()
        self.generate_tasks()
        self.split_and_write()
        self.write_readme()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--master-seed", type=int)
    parser.add_argument("--world-id", default="world-original")
    parser.add_argument("--benchmark-version", default="phase2-minimum-v2")
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing generated dataset directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = args.output_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        if not args.force:
            raise SystemExit(f"refusing to overwrite nonempty output directory: {destination}; pass --force")
        shutil.rmtree(destination)
    seeds = derived_seeds(args.master_seed) if args.master_seed is not None else dict(SEEDS)
    Gen(
        output_root=destination,
        seeds=seeds,
        world_id=args.world_id,
        benchmark_version=args.benchmark_version,
    ).run()
    print(json.dumps({"status": "pass", "output_dir": str(destination), "world_id": args.world_id, "seeds": seeds}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
