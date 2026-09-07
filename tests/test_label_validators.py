from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_evidence_labels
import verify_gold_labels

SOURCE = ROOT / "data" / "evomem_enterprise"


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


class ValidatorMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "evomem"
        shutil.copytree(SOURCE, self.data)

    def tearDown(self):
        self.temp.cleanup()

    def quiet(self, function) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return function(self.data)

    def mutate_action_gold(self, mutation) -> None:
        path = self.data / "generated" / "gold_test.jsonl"
        values = rows(path)
        target = next(value for value in values if value.get("valid_actions") or value.get("blocked_actions"))
        mutation(target)
        write_rows(path, values)

    def test_evidence_validator_detects_absent_evidence(self):
        path = self.data / "generated" / "gold_test.jsonl"
        values = rows(path)
        values[0]["eligible_assertion_ids"].append("a_absent")
        write_rows(path, values)
        self.assertEqual(self.quiet(verify_evidence_labels.main), 1)

    def test_evidence_validator_detects_required_evidence_omission(self):
        path = self.data / "generated" / "gold_test.jsonl"
        values = rows(path)
        target = next(value for value in values if value["task_id"] == "t_00022")
        target["eligible_assertion_ids"].remove("a_00527")
        write_rows(path, values)
        self.assertEqual(self.quiet(verify_evidence_labels.main), 1)

    def test_evidence_validator_rejects_malformed_valid_until(self):
        path = self.data / "generated" / "assertion_events.jsonl"
        values = rows(path)
        target = next(value for value in values if value["assertion_id"] == "a_00527")
        target["valid_until"] = "not-a-timestamp"
        write_rows(path, values)
        self.assertEqual(self.quiet(verify_evidence_labels.main), 1)

    def test_evidence_validator_checks_all_stage_fields(self):
        path = self.data / "generated" / "gold_test.jsonl"
        values = rows(path)
        values[0]["stage_labels"]["PacketEligible"] = []
        write_rows(path, values)
        self.assertEqual(self.quiet(verify_evidence_labels.main), 1)

    def test_action_validator_detects_verdict_corruption(self):
        self.mutate_action_gold(lambda gold: gold["valid_actions"].append("invented_action"))
        self.assertEqual(self.quiet(verify_gold_labels.main), 1)

    def test_action_validator_detects_witness_corruption(self):
        def mutation(gold):
            action = next(iter(gold["action_support_by_action"]))
            gold["action_support_by_action"][action] = ["a_absent"]
        self.mutate_action_gold(mutation)
        self.assertEqual(self.quiet(verify_gold_labels.main), 1)

    def test_action_validator_detects_reason_corruption(self):
        def mutation(gold):
            action = next(iter(gold["action_blocking_reasons"]))
            gold["action_blocking_reasons"][action] = ["invented_reason"]
        self.mutate_action_gold(mutation)
        self.assertEqual(self.quiet(verify_gold_labels.main), 1)

    def test_action_interpreter_rejects_cross_target_witness(self):
        task = {
            "retrieval_mode": "current_action", "target_policy_version": "refund_policy_v2",
            "candidate_actions": ["issue_refund"], "entity_scope": ["acct_A", "case_A", "acct_B"],
            "workflow_instance_id": "case_A",
        }
        def fact(aid, subject, relation, value, workflow=None, kind="semantic_fact"):
            return {"assertion_id": aid, "subject": subject, "predicate": relation, "object": value,
                    "assertion_type": kind, "entity_scope": [subject], "workflow_instance_id": workflow,
                    "record_time": "2026-05-01T00:00:00Z"}
        evidence = [
            fact("sub_A", "acct_A", "subscription_status", "suspended"),
            fact("sub_B", "acct_B", "subscription_status", "active"),
            fact("wf_A", "case_A", "workflow_state", "approved", "case_A", "workflow_fact"),
        ]
        registry = {"issue_refund": {"kind": "effectful", "policy_family": "refund", "workflow_type": "refund"}}
        policies = {"refund_policy_v2": [{"action": "issue_refund", "policy_family": "refund", "priority": 1,
            "permit_or_deny": "permit", "guard": {"equals": ["subscription_status", "active"]}}]}
        workflows = {"refund": {"transitions": [{"action": "issue_refund", "from": "approved", "to": "refunded"}]}}
        valid, blocked, _, reasons = verify_gold_labels.expected_actions(
            task, evidence, [], registry, policies, workflows
        )
        self.assertNotIn("issue_refund", valid)
        self.assertIn("issue_refund", blocked)
        self.assertIn("policy_guard_failed", reasons["issue_refund"])

    def _membership_world(self):
        task = {
            "retrieval_mode": "current_action", "target_policy_version": "refund_policy_v2",
            "candidate_actions": ["issue_refund"], "entity_scope": ["acct_A", "case_A", "acct_B"],
            "workflow_instance_id": "case_A",
        }

        def fact(aid, subject, relation, value, workflow=None, kind="semantic_fact",
                 source="billing", scope=None):
            return {"assertion_id": aid, "subject": subject, "predicate": relation, "object": value,
                    "assertion_type": kind, "entity_scope": [subject] if scope is None else list(scope),
                    "workflow_instance_id": workflow, "source": source,
                    "record_time": "2026-05-01T00:00:00Z"}

        evidence = [
            fact("sub_A", "acct_A", "subscription_status", "suspended"),
            fact("sub_B", "acct_B", "subscription_status", "active"),
            fact("wf_A", "case_A", "workflow_state", "approved", "case_A", "workflow_fact",
                 source="workflow_log", scope=["case_A", "acct_A"]),
        ]
        registry = {"issue_refund": {"kind": "effectful", "policy_family": "refund", "workflow_type": "refund"}}
        policies = {"refund_policy_v2": [{"action": "issue_refund", "policy_family": "refund", "priority": 1,
            "permit_or_deny": "permit", "guard": {"equals": ["subscription_status", "active"]}}]}
        workflows = {"refund": {"transitions": [{"action": "issue_refund", "from": "approved", "to": "refunded"}]}}
        trust = json.loads((SOURCE / "config" / "trust_precedence.json").read_text())["relations"]
        return task, evidence, fact, registry, policies, workflows, trust

    def test_action_interpreter_rejects_untrusted_workflow_membership(self):
        """Only a source trusted for workflow_state may enrol an entity in a case.

        The billing-sourced workflow record below carries the case identifier and
        names the second account. Admitting it as a membership declaration lets
        that account's active subscription satisfy the refund guard.
        """
        task, evidence, fact, registry, policies, workflows, trust = self._membership_world()
        evidence.append(fact("wf_forged", "case_A", "workflow_state", "approved", "case_A",
                             "workflow_fact", source="billing", scope=["acct_B"]))
        binding = verify_gold_labels.action_binding(task, evidence, trust)
        self.assertNotIn("acct_B", binding.get("members") or [])
        valid, blocked, support, _ = verify_gold_labels.expected_actions(
            task, evidence, [], registry, policies, workflows, trust
        )
        self.assertNotIn("issue_refund", valid)
        self.assertIn("issue_refund", blocked)
        for witnesses in support.values():
            self.assertNotIn("sub_B", witnesses)

    def test_action_interpreter_keeps_trusted_workflow_membership(self):
        """The restriction must not reject membership a trusted record declares."""
        task, evidence, _, registry, policies, workflows, trust = self._membership_world()
        evidence[0]["object"] = "active"
        binding = verify_gold_labels.action_binding(task, evidence, trust)
        self.assertIn("acct_A", binding.get("members") or [])
        self.assertFalse(binding["ambiguous"])
        valid, _, support, _ = verify_gold_labels.expected_actions(
            task, evidence, [], registry, policies, workflows, trust
        )
        self.assertIn("issue_refund", valid)
        self.assertIn("sub_A", support["issue_refund"])

    def test_evidence_validator_detects_contradiction_winner_omission(self):
        """Emptying a contradiction task's winner must not read as a clean pass.

        Every duplicated evidence-stage field is cleared, so agreement among
        them cannot stand in for completeness; the task-specific required answer
        is what exposes the omission.
        """
        path = self.data / "generated" / "gold_test.jsonl"
        values = rows(path)
        target = next(value for value in values if value["task_id"] == "t_00102")
        for field in ("eligible_assertion_ids", "assertion_eligible_ids",
                      "packet_eligible_assertion_ids", "resolved_eligible_assertion_ids",
                      "contradiction_winner_ids"):
            if field in target:
                target[field] = []
        write_rows(path, values)
        self.assertEqual(self.quiet(verify_evidence_labels.main), 1)

    def test_action_interpreter_blocks_critical_unresolved_conflict(self):
        task = {"retrieval_mode": "current_action", "target_policy_version": "p", "candidate_actions": ["act"],
                "entity_scope": ["acct_A"], "workflow_instance_id": None}
        evidence = [{"assertion_id": "s", "subject": "acct_A", "predicate": "subscription_status",
                     "object": "active", "assertion_type": "semantic_fact", "entity_scope": ["acct_A"],
                     "record_time": "2026-05-01T00:00:00Z"},
                    {"assertion_id": "w", "subject": "acct_A", "predicate": "workflow_state",
                     "object": "ready", "assertion_type": "workflow_fact", "entity_scope": ["acct_A"],
                     "record_time": "2026-05-01T00:00:00Z"}]
        registry = {"act": {"kind": "effectful", "policy_family": "f", "workflow_type": "wf"}}
        policies = {"p": [{"action": "act", "policy_family": "f", "priority": 1,
                            "permit_or_deny": "permit", "guard": {"equals": ["subscription_status", "active"]}}]}
        workflows = {"wf": {"transitions": [{"action": "act", "from": "ready", "to": "done"}]}}
        unresolved = [{"predicate": "subscription_status", "key": ["acct_A", "subscription_status"]}]
        valid, _, _, reasons = verify_gold_labels.expected_actions(
            task, evidence, unresolved, registry, policies, workflows
        )
        self.assertNotIn("act", valid)
        self.assertIn("critical_unresolved_conflict", reasons["act"])

    def test_validation_is_read_only(self):
        before = (self.data / "generated" / "gold_test.jsonl").read_bytes()
        self.assertEqual(self.quiet(verify_evidence_labels.main), 0)
        self.assertEqual(self.quiet(verify_gold_labels.main), 0)
        after = (self.data / "generated" / "gold_test.jsonl").read_bytes()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
