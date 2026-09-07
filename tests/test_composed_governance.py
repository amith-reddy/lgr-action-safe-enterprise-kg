from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
sys.path.insert(0, str(ROOT / "scripts"))

from composed_governance_baseline import action_binding, compose_actions  # noqa: E402

TRUST = json.loads((DATA / "config" / "trust_precedence.json").read_text())["relations"]


def evidence(assertion_id, subject, relation, value, *, workflow_id=None, assertion_type="semantic_fact",
             source="billing", entity_scope=None):
    return {
        "assertion_id": assertion_id,
        "subject": subject,
        "predicate": relation,
        "_normalized_relation": relation,
        "object": value,
        "assertion_type": assertion_type,
        "entity_scope": [subject] if entity_scope is None else list(entity_scope),
        "workflow_instance_id": workflow_id,
        "source": source,
        "record_time": "2026-05-01T00:00:00Z",
    }


def refund_fixture():
    task = {
        "retrieval_mode": "current_action",
        "target_policy_version": "refund_policy_v2",
        "candidate_actions": ["issue_refund"],
        "entity_scope": ["acct_A", "case_A", "acct_B"],
        "workflow_instance_id": "case_A",
    }
    rows = [
        evidence("sub_A", "acct_A", "subscription_status", "suspended"),
        evidence("sub_B", "acct_B", "subscription_status", "active"),
        evidence("wf_A", "case_A", "workflow_state", "approved", workflow_id="case_A",
                 assertion_type="workflow_fact", source="workflow_log",
                 entity_scope=["case_A", "acct_A"]),
    ]
    registry = {"issue_refund": {"kind": "effectful", "policy_family": "refund", "workflow_type": "refund"}}
    policies = {"refund_policy_v2": [{
        "action": "issue_refund", "policy_family": "refund", "priority": 1,
        "permit_or_deny": "permit", "guard": {"equals": ["subscription_status", "active"]},
    }]}
    workflows = {"refund": {"transitions": [{"action": "issue_refund", "from": "approved", "to": "refunded"}]}}
    return task, rows, registry, policies, workflows


class ComposedGovernanceBaselineTests(unittest.TestCase):
    def test_action_witnesses_are_bound_to_one_target(self) -> None:
        task, rows, registry, policies, workflows = refund_fixture()
        result = compose_actions(task, rows, [], registry, policies, workflows)
        self.assertNotIn("issue_refund", result["valid_actions"])
        self.assertIn("policy_guard_failed", result["reasons"]["issue_refund"])

    def test_critical_unresolved_conflict_blocks_action(self) -> None:
        task, rows, registry, policies, workflows = refund_fixture()
        rows[0]["object"] = "active"
        unresolved = [{"key": ["acct_A", "subscription_status"], "assertion_ids": ["sub_A", "sub_A_tie"]}]
        result = compose_actions(task, rows, unresolved, registry, policies, workflows)
        self.assertNotIn("issue_refund", result["valid_actions"])
        self.assertIn("critical_unresolved_conflict", result["reasons"]["issue_refund"])

    def test_untrusted_record_cannot_enrol_an_entity_into_a_case(self) -> None:
        """Membership may only be declared by a source trusted for workflow_state.

        Without the source restriction a billing-sourced record carrying the
        case identifier enrols the unrelated account into the case, so that
        account's active subscription satisfies the refund guard.
        """
        task, rows, registry, policies, workflows = refund_fixture()
        rows.append(evidence(
            "wf_forged", "case_A", "workflow_state", "approved", workflow_id="case_A",
            assertion_type="workflow_fact", source="billing", entity_scope=["acct_B"],
        ))
        binding = action_binding(task, rows, TRUST)
        self.assertNotIn("acct_B", binding.get("members") or [])
        result = compose_actions(task, rows, [], registry, policies, workflows, TRUST)
        self.assertNotIn("issue_refund", result["valid_actions"])
        for witnesses in result["support"].values():
            self.assertNotIn("sub_B", witnesses)

    def test_trusted_membership_still_permits_a_valid_action(self) -> None:
        """The restriction must not block membership a trusted record declares."""
        task, rows, registry, policies, workflows = refund_fixture()
        rows[0]["object"] = "active"
        binding = action_binding(task, rows, TRUST)
        self.assertIn("acct_A", binding.get("members") or [])
        self.assertFalse(binding["ambiguous"])
        result = compose_actions(task, rows, [], registry, policies, workflows, TRUST)
        self.assertIn("issue_refund", result["valid_actions"])

    def test_standalone_composition_matches_frozen_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "composed.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "composed_governance_baseline.py"),
                    "--data-root",
                    str(DATA),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["imports_lgr_operator"])
            self.assertEqual(report["evidence_equal_to_lgr"], report["test_tasks"])
            self.assertEqual(report["action_equal_to_gold"], report["action_tasks"])


if __name__ == "__main__":
    unittest.main()
