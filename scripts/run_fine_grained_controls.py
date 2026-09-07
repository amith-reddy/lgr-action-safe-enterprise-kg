#!/usr/bin/env python3
"""Exercise controls that were previously coupled under broad ablation flags.

Each case changes one explicit control while keeping the remaining controls on.
The report is a targeted conformance diagnostic, not a population estimate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lgr_operator import (  # noqa: E402
    GovernanceBundle,
    admit_actions,
    eligibility_reasons,
    resolve_conflicts,
)

DEFAULT_DATA = ROOT / "data" / "evomem_enterprise"
DEFAULT_OUTPUT = ROOT / "experiments" / "lgr_jws" / "fine_grained_controls.json"

FULL = {
    "use_entity_scope": True,
    "use_relation_scope": True,
    "use_record_visibility": True,
    "use_validity_interval": True,
    "use_lifecycle_state": True,
    "use_provenance_activity": True,
    "use_source_eligibility": True,
    "use_ontology_versioning": True,
    "use_policy_versioning": True,
    "use_supersession_links": True,
    "use_contradiction_resolver": True,
    "use_conflict_trust": True,
    "use_workflow_instance_scope": True,
    "use_action_target_binding": True,
}


def assertion(assertion_id: str, obj: str = "active", **overrides) -> dict:
    row = {
        "assertion_id": assertion_id,
        "subject": "acct_A",
        "predicate": "subscription_status",
        "object": obj,
        "assertion_type": "semantic_fact",
        "entity_scope": ["acct_A"],
        "event_time": "2026-05-01T00:00:00Z",
        "record_time": "2026-05-01T00:05:00Z",
        "valid_from": "2026-05-01T00:00:00Z",
        "valid_until": None,
        "ontology_version": "ov_3",
        "policy_version": "refund_policy_v2",
        "provenance_activity": "pa_a_00001",
        "source": "billing",
        "lifecycle_state": "active",
        "supersedes": [],
        "superseded_by": [],
        "workflow_instance_id": None,
    }
    row.update(overrides)
    return row


def query(**overrides) -> dict:
    row = {
        "task_id": "fine_grained_control",
        "task_type": "current_factual_recall",
        "decision_time": "2026-06-01T00:00:00Z",
        "entity_scope": ["acct_A"],
        "relation_scope": ["subscription_status"],
        "target_ontology_version": "ov_3",
        "target_policy_version": "refund_policy_v2",
        "trust_table_version": "trust-v1",
        "retrieval_mode": "current_action",
        "disallowed_sources": [],
        "candidate_actions": [],
        "workflow_instance_id": None,
    }
    row.update(overrides)
    return row


def eligibility_case(governance, name, flag, expected, row, task) -> dict:
    index = {row["assertion_id"]: row}
    full_reasons = eligibility_reasons(row, task, FULL, governance, index)
    disabled = dict(FULL)
    disabled[flag] = False
    disabled_reasons = eligibility_reasons(row, task, disabled, governance, index)
    passed = full_reasons == [expected] and disabled_reasons == []
    return {
        "control": name,
        "flag": flag,
        "expected_sole_reason": expected,
        "full_reasons": full_reasons,
        "disabled_reasons": disabled_reasons,
        "status": "pass" if passed else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    governance = GovernanceBundle.load(args.data_root.resolve())
    results = []

    results.append(eligibility_case(
        governance, "record visibility", "use_record_visibility", "record_not_visible",
        assertion("future_record", record_time="2026-06-02T00:00:00Z"), query(),
    ))
    results.append(eligibility_case(
        governance, "valid-time interval", "use_validity_interval", "time_invalid",
        assertion("expired_fact", valid_until="2026-05-15T00:00:00Z"), query(),
    ))
    results.append(eligibility_case(
        governance, "provenance activity", "use_provenance_activity", "provenance_missing",
        assertion("missing_activity", provenance_activity=None), query(),
    ))
    results.append(eligibility_case(
        governance, "source eligibility", "use_source_eligibility", "source_disallowed",
        assertion("disallowed_source"), query(disallowed_sources=["billing"]),
    ))
    results.append(eligibility_case(
        governance, "workflow-instance scope", "use_workflow_instance_scope", "workflow_instance_mismatch",
        assertion("wrong_case", workflow_instance_id="case_B"), query(workflow_instance_id="case_A"),
    ))

    high = assertion("high_authority_old", "active", source="billing", record_time="2026-05-01T00:05:00Z")
    low = assertion(
        "low_authority_new", "cancelled", source="crm", provenance_activity="pa_a_00005",
        record_time="2026-05-20T00:05:00Z",
    )
    resolved_full, _, _, _ = resolve_conflicts([high, low], query(), governance, use_trust=True)
    resolved_no_trust, _, _, _ = resolve_conflicts([high, low], query(), governance, use_trust=False)
    trust_pass = [r["assertion_id"] for r in resolved_full] == ["high_authority_old"] and [
        r["assertion_id"] for r in resolved_no_trust
    ] == ["low_authority_new"]
    results.append({
        "control": "relation-specific trust precedence",
        "flag": "use_conflict_trust",
        "full_winners": [r["assertion_id"] for r in resolved_full],
        "disabled_winners": [r["assertion_id"] for r in resolved_no_trust],
        "status": "pass" if trust_pass else "fail",
    })

    suspended = assertion("sub_A", "suspended")
    workflow = assertion(
        "wf_A", "approved", subject="case_A", predicate="workflow_state",
        source="workflow_log", provenance_activity="pa_a_00009",
        assertion_type="workflow_fact", entity_scope=["acct_A"], workflow_instance_id="case_A",
    )
    unrelated = assertion(
        "sub_B", "active", subject="acct_B", entity_scope=["acct_B"],
        provenance_activity="pa_a_00002",
    )
    action_task = query(
        task_type="policy_valid_refund_action",
        entity_scope=["acct_A", "case_A", "acct_B"],
        relation_scope=["subscription_status", "workflow_state"],
        candidate_actions=["issue_refund"], workflow_instance_id="case_A",
    )
    bound = admit_actions([suspended, workflow, unrelated], action_task, governance, [], enforce_binding=True)
    unbound = admit_actions([suspended, workflow, unrelated], action_task, governance, [], enforce_binding=False)
    binding_pass = "issue_refund" not in bound["valid_actions"] and "issue_refund" in unbound["valid_actions"]
    results.append({
        "control": "action-target binding",
        "flag": "use_action_target_binding",
        "full_valid_actions": bound["valid_actions"],
        "disabled_valid_actions": unbound["valid_actions"],
        "status": "pass" if binding_pass else "fail",
    })

    failures = [row["control"] for row in results if row["status"] != "pass"]
    report = {
        "status": "pass" if not failures else "fail",
        "purpose": "Targeted isolation of controls formerly coupled by broad ablation flags.",
        "population_claim": "None; these are constructed decisive cases.",
        "controls_tested": len(results),
        "results": results,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
