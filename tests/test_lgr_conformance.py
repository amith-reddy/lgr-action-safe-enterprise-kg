from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lgr_operator import (  # noqa: E402
    GovernanceBundle,
    admit_actions,
    action_binding,
    conflict_key,
    decision_evidence_completion,
    decision_record,
    decision_scope_relations,
    eligibility_reasons,
    evaluate_lgr,
    normalization_candidates,
    normalized_relation,
    resolve_conflicts,
    snapshot_manifest,
    validate_trust_table,
    validate_supersession_graph,
)
from run_phase3_experiments import retrieve  # noqa: E402


DATA = ROOT / "data" / "evomem_enterprise"


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def assertion(assertion_id: str, obj: str, **overrides) -> dict:
    row = {
        "assertion_id": assertion_id,
        "subject": "acct_001",
        "predicate": "subscription_status",
        "object": obj,
        "assertion_type": "semantic_fact",
        "entity_scope": ["acct_001"],
        "event_time": "2026-05-01T00:00:00Z",
        "record_time": "2026-05-01T00:05:00Z",
        "valid_from": "2026-05-01T00:00:00Z",
        "valid_until": None,
        "ontology_version": "ov_3",
        "policy_version": "refund_policy_v2",
        "provenance_activity": f"pa_{assertion_id}",
        "source": "billing",
        "lifecycle_state": "active",
        "superseded_by": [],
        "workflow_instance_id": None,
    }
    row.update(overrides)
    return row


def query(**overrides) -> dict:
    row = {
        "task_id": "unit",
        "task_type": "current_factual_recall",
        "decision_time": "2026-06-01T00:00:00Z",
        "entity_scope": ["acct_001"],
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


CFG = {
    "use_entity_scope": True,
    "use_relation_scope": True,
    "use_validity_interval": True,
    "use_lifecycle_state": True,
    "use_provenance_trust": True,
    "use_ontology_versioning": True,
    "use_policy_versioning": True,
    "use_supersession_links": True,
    "use_contradiction_resolver": True,
    "use_workflow_state_binding": True,
}


class LGRConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.governance = GovernanceBundle.load(DATA)

    def test_all_eight_eligibility_predicates_have_negative_cases(self) -> None:
        cases = [
            (assertion("a_scope", "active", subject="other", entity_scope=["other"]), "scope_entity_mismatch"),
            (assertion("a_relation", "active", predicate="unknown_relation"), "scope_relation_mismatch"),
            (assertion("a_time", "active", valid_until="2026-05-15T00:00:00Z"), "time_invalid"),
            (assertion("a_future_record", "active", record_time="2026-06-02T00:00:00Z"), "record_not_visible"),
            (assertion("a_life", "active", lifecycle_state="expired"), "lifecycle_ineligible"),
            (assertion("a_ont", "active", ontology_version="ov_0"), "ontology_incompatible"),
            (
                assertion(
                    "a_policy",
                    "active",
                    assertion_type="policy_fact",
                    policy_version="refund_policy_v1",
                ),
                "policy_version_incompatible",
            ),
            (assertion("a_prov", "active", provenance_activity=None, source=None), "provenance_missing"),
            (assertion("a_source", "active", source="billing"), "source_disallowed"),
            (assertion("a_untrusted", "active", source="unknown_source"), "source_untrusted"),
            (assertion("a_sup", "active", superseded_by=["a_new"]), "superseded"),
        ]
        for row, expected in cases:
            task = query(disallowed_sources=["billing"] if expected == "source_disallowed" else [])
            with self.subTest(expected=expected):
                self.assertIn(expected, eligibility_reasons(row, task, CFG, self.governance))

    def test_newest_record_wins_within_same_trust_tier(self) -> None:
        older = assertion("a_old", "active", record_time="2026-05-01T00:05:00Z")
        newer = assertion("a_new", "suspended", record_time="2026-05-02T00:05:00Z")
        resolved, suppressed, unresolved, _ = resolve_conflicts(
            [older, newer], query(), self.governance
        )
        self.assertEqual([row["assertion_id"] for row in resolved], ["a_new"])
        self.assertEqual(suppressed["a_old"], ["contradiction_loser"])
        self.assertEqual(unresolved, [])

    def test_equal_authority_equal_time_conflict_is_unresolved(self) -> None:
        first = assertion("a_first", "active")
        second = assertion("a_second", "suspended")
        resolved, suppressed, unresolved, _ = resolve_conflicts(
            [first, second], query(), self.governance
        )
        self.assertEqual(resolved, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(suppressed["a_first"], ["unresolved_conflict"])
        self.assertEqual(suppressed["a_second"], ["unresolved_conflict"])

    def test_trust_validator_rejects_duplicate_missing_and_version_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate tiers"):
            validate_trust_table({"version": "v1", "relations": {"p": ["a", "a"]}})
        with self.assertRaisesRegex(ValueError, "missing relations"):
            validate_trust_table(
                {"version": "v1", "relations": {"p": ["a"]}},
                required_relations=["q"],
            )
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            validate_trust_table(
                {"version": "v1", "relations": {"p": ["a"]}},
                expected_version="v2",
            )
        with self.assertRaisesRegex(ValueError, "missing relation/source pairs"):
            validate_trust_table(
                {"version": "v1", "relations": {"p": ["a"]}},
                required_pairs=[("p", "b")],
            )

    def test_smoke_refund_label_is_table_conformant(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        gold = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "gold_smoke.jsonl")}
        assertions = {row["assertion_id"]: row for row in read_jsonl(DATA / "generated" / "assertion_events.jsonl")}
        task = tasks["t_00041"]
        evidence = [assertions[item] for item in gold["t_00041"]["eligible_assertion_ids"]]
        result = admit_actions(evidence, task, self.governance, [])
        self.assertEqual(result["valid_actions"], ["request_manager_approval", "deny_refund"])
        self.assertEqual(result["blocked_actions"], ["issue_refund"])
        self.assertTrue(result["support_by_action"]["request_manager_approval"])

    def test_unregistered_action_is_default_denied(self) -> None:
        result = admit_actions([], query(candidate_actions=["transfer_funds"]), self.governance, [])
        self.assertEqual(result["valid_actions"], [])
        self.assertEqual(result["blocking_reasons"]["transfer_funds"], ["unregistered_action"])

    def test_registered_advisory_action_needs_no_policy_or_workflow_binding(self) -> None:
        actions = dict(self.governance.actions)
        actions["explain_decision"] = {
            "action": "explain_decision",
            "kind": "advisory",
        }
        governance = replace(self.governance, actions=actions)
        result = admit_actions(
            [],
            query(candidate_actions=["explain_decision"]),
            governance,
            [],
        )
        self.assertEqual(result["valid_actions"], ["explain_decision"])
        self.assertEqual(result["support_by_action"]["explain_decision"], [])
        self.assertEqual(
            result["bindings_consulted"]["explain_decision"]["action_kind"],
            "advisory",
        )

    def test_effectful_action_rejects_cross_family_same_name_policy_rule(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        gold = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "gold_smoke.jsonl")}
        assertions = {row["assertion_id"]: row for row in read_jsonl(DATA / "generated" / "assertion_events.jsonl")}
        task = dict(tasks["t_00041"])
        task["candidate_actions"] = ["request_manager_approval"]
        task["target_policy_version"] = "sla_policy_v2"
        evidence = [assertions[item] for item in gold["t_00041"]["eligible_assertion_ids"]]
        policies = {version: list(rules) for version, rules in self.governance.policies.items()}
        policies["sla_policy_v2"].append(
            {
                "policy_version": "sla_policy_v2",
                "policy_family": "sla",
                "action": "request_manager_approval",
                "permit_or_deny": "permit",
                "priority": 99,
                "guard": {"equals": ["workflow_state", "eligibility_checked"]},
            }
        )
        governance = replace(self.governance, policies=policies)
        result = admit_actions(evidence, task, governance, [])
        self.assertEqual(result["valid_actions"], [])
        self.assertIn(
            "policy_family_mismatch",
            result["blocking_reasons"]["request_manager_approval"],
        )

    def test_invalid_supersession_link_cannot_suppress_evidence(self) -> None:
        row = assertion("a_current", "active", superseded_by=["missing"])
        reasons = eligibility_reasons(
            row,
            query(),
            CFG,
            self.governance,
            {row["assertion_id"]: row},
        )
        self.assertNotIn("superseded", reasons)

    def test_visible_successor_permanently_suppresses_predecessor(self) -> None:
        predecessor = assertion("a_old", "active", superseded_by=["a_new"])
        valid_successor = assertion("a_new", "suspended")
        index = {"a_old": predecessor, "a_new": valid_successor}
        self.assertIn(
            "superseded",
            eligibility_reasons(predecessor, query(), CFG, self.governance, index),
        )

        ineligible_successors = [
            assertion("a_new", "suspended", lifecycle_state="expired"),
            assertion("a_new", "suspended", provenance_activity=None, source=None),
            assertion("a_new", "suspended", source="unknown_source"),
            assertion(
                "a_new",
                "suspended",
                assertion_type="policy_fact",
                policy_version="refund_policy_v1",
            ),
            assertion("a_new", "suspended", ontology_version="ov_0"),
        ]
        for successor in ineligible_successors:
            with self.subTest(successor=successor):
                index = {"a_old": predecessor, "a_new": successor}
                reasons = eligibility_reasons(
                    predecessor,
                    query(),
                    CFG,
                    self.governance,
                    index,
                )
                self.assertIn("superseded", reasons)

    def test_future_successor_does_not_change_an_earlier_decision(self) -> None:
        predecessor = assertion("a_old", "active", superseded_by=["a_future"])
        successor = assertion("a_future", "suspended", record_time="2026-06-02T00:00:00Z")
        reasons = eligibility_reasons(
            predecessor,
            query(),
            CFG,
            self.governance,
            {"a_old": predecessor, "a_future": successor},
        )
        self.assertNotIn("superseded", reasons)

    def test_conflict_key_excludes_value_and_multi_value_relation_does_not_conflict(self) -> None:
        first = assertion("a_one", "primary", predicate="support_contact")
        second = assertion("a_two", "billing", predicate="support_contact")
        contact_query = query(relation_scope=["support_contact"])
        self.assertEqual(conflict_key(first, contact_query, self.governance), None)
        resolved, suppressed, unresolved, trace = resolve_conflicts(
            [first, second], contact_query, self.governance
        )
        self.assertEqual([row["assertion_id"] for row in resolved], ["a_one", "a_two"])
        self.assertEqual(suppressed, {})
        self.assertEqual(unresolved, [])
        self.assertEqual(trace, [])

    def test_conflict_key_groups_distinct_single_values_without_using_object(self) -> None:
        first = assertion("a_one", "active")
        second = assertion("a_two", "suspended")
        self.assertEqual(
            conflict_key(first, query(), self.governance),
            conflict_key(second, query(), self.governance),
        )

    def test_decision_completion_includes_guard_dependencies_not_just_query_relations(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = dict(tasks["t_00041"])
        task["relation_scope"] = ["support_entitlement"]
        completed, manifest = decision_evidence_completion(assertions, task, self.governance)
        self.assertEqual(manifest["status"], "complete_for_declared_snapshot")
        self.assertIn("workflow_state", manifest["dependency_relations"])
        self.assertTrue(any(row.get("predicate") == "workflow_state" for row in completed))

    def test_common_gate_uses_authoritative_completion_not_top_k_context(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = tasks["t_00041"]
        snapshot = snapshot_manifest(DATA)
        lexical = retrieve("lexical_top_k_memory", "smoke", task, assertions, {}, self.governance, snapshot)
        lgr = retrieve("lifecycle_governed_kg_retrieval", "smoke", task, assertions, {}, self.governance, snapshot)
        self.assertLessEqual(len(lexical["initial_retrieved_assertion_ids"]), 8)
        self.assertEqual(lexical["decision_evidence_status"], "complete_for_declared_snapshot")
        self.assertEqual(lexical["predicted_valid_actions"], lgr["predicted_valid_actions"])
        self.assertEqual(lexical["predicted_blocked_actions"], lgr["predicted_blocked_actions"])

    def test_supersession_graph_rejects_cycles_and_cross_subject_links(self) -> None:
        first = assertion("a_one", "active", superseded_by=["a_two"])
        second = assertion("a_two", "suspended", superseded_by=["a_one"])
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_supersession_graph({"a_one": first, "a_two": second})
        other = assertion("a_other", "suspended", subject="acct_999")
        with self.assertRaisesRegex(ValueError, "crosses subjects"):
            validate_supersession_graph({"a_one": first, "a_two": other})

    def test_equal_priority_policy_deny_overrides_permit(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        gold = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "gold_smoke.jsonl")}
        assertions = {row["assertion_id"]: row for row in read_jsonl(DATA / "generated" / "assertion_events.jsonl")}
        task = dict(tasks["t_00041"])
        task["candidate_actions"] = ["request_manager_approval"]
        evidence = [assertions[item] for item in gold["t_00041"]["eligible_assertion_ids"]]
        policies = {version: list(rules) for version, rules in self.governance.policies.items()}
        policies["refund_policy_v2"].append(
            {
                "policy_version": "refund_policy_v2",
                "policy_family": "refund",
                "action": "request_manager_approval",
                "permit_or_deny": "deny",
                "priority": 8,
                "guard": {"equals": ["workflow_state", "eligibility_checked"]},
            }
        )
        governance = replace(self.governance, policies=policies)
        result = admit_actions(evidence, task, governance, [])
        self.assertEqual(result["valid_actions"], [])
        self.assertIn("policy_deny", result["blocking_reasons"]["request_manager_approval"])

    def test_witness_and_reason_traces_are_nonempty(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = tasks["t_00041"]
        evaluated = evaluate_lgr(assertions, task, CFG, self.governance, top_k=8)
        self.assertTrue(evaluated["suppression_reasons"])
        self.assertTrue(all(evaluated["suppression_reasons"].values()))
        self.assertTrue(evaluated["valid_actions"])
        self.assertTrue(all(evaluated["support_by_action"][action] for action in evaluated["valid_actions"]))

        denied = admit_actions([], task, self.governance, [])
        self.assertEqual(denied["valid_actions"], [])
        self.assertTrue(all(denied["blocking_reasons"][action] for action in denied["blocked_actions"]))

    def test_replay_is_deterministic_and_snapshot_detects_mutation(self) -> None:
        tasks = read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = next(row for row in tasks if row["task_id"] == "t_00041")
        first = evaluate_lgr(assertions, task, CFG, self.governance, top_k=8)
        second = evaluate_lgr(assertions, task, CFG, self.governance, top_k=8)
        self.assertEqual(first, second)
        stable_one = snapshot_manifest(DATA)
        stable_two = snapshot_manifest(DATA)
        self.assertEqual(stable_one, stable_two)

        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "evomem"
            shutil.copytree(DATA, copied)
            trust_path = copied / "config" / "trust_precedence.json"
            trust = json.loads(trust_path.read_text(encoding="utf-8"))
            trust["version"] = "trust-mutated"
            trust_path.write_text(json.dumps(trust), encoding="utf-8")
            self.assertNotEqual(stable_one["snapshot_id"], snapshot_manifest(copied)["snapshot_id"])


class AdmissionSoundnessTests(unittest.TestCase):
    """Regressions for admission properties the aggregate metrics cannot see.

    Each case below is a counterexample that the operator previously admitted
    or suppressed incorrectly.  They test joint validity of a justification,
    not the validity of individual assertions.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.governance = GovernanceBundle.load(DATA)

    # --- guard witnesses must concern one principal -------------------------

    def _two_account_world(self):
        suspended = assertion(
            "a_sub_A", "suspended", subject="acct_A", entity_scope=["acct_A"],
            provenance_activity="pa_a_00001", source="billing",
        )
        approved = assertion(
            "a_wf_A", "approved", subject="case_A", predicate="workflow_state",
            source="workflow_log", entity_scope=["acct_A"], workflow_instance_id="case_A",
            provenance_activity="pa_a_00009", assertion_type="workflow_fact",
        )
        other = assertion(
            "a_sub_B", "active", subject="acct_B", entity_scope=["acct_B"],
            provenance_activity="pa_a_00002", source="billing",
        )
        task = query(
            task_type="policy_valid_refund_action",
            entity_scope=["acct_A", "case_A"],
            relation_scope=["subscription_status", "workflow_state"],
            candidate_actions=["issue_refund"],
            workflow_instance_id="case_A",
        )
        return suspended, approved, other, task

    def test_unrelated_entity_cannot_supply_a_guard_witness(self) -> None:
        suspended, approved, other, task = self._two_account_world()
        alone = evaluate_lgr([suspended, approved], task, CFG, self.governance, top_k=8)
        self.assertEqual(alone["valid_actions"], [])

        widened = dict(task)
        widened["entity_scope"] = ["acct_A", "case_A", "acct_B"]
        mixed = evaluate_lgr([suspended, approved, other], widened, CFG, self.governance, top_k=8)
        self.assertEqual(
            mixed["valid_actions"], [],
            "another account's subscription status must not authorize this refund",
        )
        for witnesses in mixed["support_by_action"].values():
            self.assertNotIn("a_sub_B", witnesses)

    def test_colliding_identifier_suffix_does_not_confer_membership(self) -> None:
        """Identifier spelling must not establish authorization.

        An earlier binding rule resolved case membership by comparing the
        trailing segment of identifiers, so any entity whose name happened to
        end in the case's suffix was treated as part of that case.  Naming an
        unrelated account `unrelated_A` was enough to authorize a refund on
        `case_A` with the unrelated account's active subscription.
        """
        suspended, approved, _, task = self._two_account_world()
        colliding = assertion(
            "a_sub_collide", "active", subject="unrelated_A", entity_scope=["unrelated_A"],
            provenance_activity="pa_a_00002", source="billing",
        )
        widened = dict(task)
        widened["entity_scope"] = ["acct_A", "case_A", "unrelated_A"]
        result = evaluate_lgr([suspended, approved, colliding], widened, CFG, self.governance, top_k=8)
        self.assertEqual(
            result["valid_actions"], [],
            "an entity sharing the case's identifier suffix must not authorize its action",
        )
        for witnesses in result["support_by_action"].values():
            self.assertNotIn("a_sub_collide", witnesses)

        binding = action_binding(widened, [suspended, approved, colliding], self.governance)
        self.assertNotIn("unrelated_A", binding.get("members") or [])
        self.assertEqual(binding.get("membership_basis"), "declared_workflow_membership")

    def test_membership_survives_renaming_the_case_identifier(self) -> None:
        """Binding follows declared membership, not a shared naming convention."""
        suspended, approved, _, task = self._two_account_world()
        renamed_wf = dict(approved)
        renamed_wf["workflow_instance_id"] = "ticket-77Z"
        renamed_wf["subject"] = "ticket-77Z"
        renamed_task = dict(task)
        renamed_task["workflow_instance_id"] = "ticket-77Z"
        binding = action_binding(renamed_task, [suspended, renamed_wf], self.governance)
        self.assertIn("acct_A", binding["members"])
        self.assertFalse(binding["ambiguous"])

    def test_untrusted_record_cannot_enrol_an_entity_into_a_case(self) -> None:
        """Only the workflow's own trusted records may declare participants."""
        suspended, approved, _, task = self._two_account_world()
        forged = assertion(
            "a_forged", "approved", subject="case_A", predicate="workflow_state",
            source="user_note", entity_scope=["acct_B"], workflow_instance_id="case_A",
            assertion_type="workflow_fact",
        )
        widened = dict(task)
        widened["entity_scope"] = ["acct_A", "case_A", "acct_B"]
        binding = action_binding(widened, [suspended, approved, forged], self.governance)
        self.assertNotIn("acct_B", binding["members"])

    def test_action_binding_refuses_an_unresolvable_target(self) -> None:
        binding = action_binding({"entity_scope": ["acct_A", "acct_B"], "workflow_instance_id": None})
        self.assertTrue(binding["ambiguous"])
        suspended, approved, other, task = self._two_account_world()
        ambiguous = dict(task)
        ambiguous["entity_scope"] = ["acct_A", "acct_B"]
        ambiguous["workflow_instance_id"] = None
        result = admit_actions([suspended, approved, other], ambiguous, self.governance, [])
        self.assertEqual(result["valid_actions"], [])
        self.assertIn("ambiguous_action_binding", result["blocking_reasons"]["issue_refund"])

    # --- completed dependencies must survive eligibility --------------------

    def test_guard_dependency_survives_a_narrowed_retrieval_scope(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        wide = tasks["t_00041"]
        narrow = dict(wide)
        narrow["relation_scope"] = ["support_entitlement"]

        self.assertIn("workflow_state", decision_scope_relations(narrow, self.governance))
        wide_result = evaluate_lgr(assertions, wide, CFG, self.governance, top_k=8)
        narrow_result = evaluate_lgr(assertions, narrow, CFG, self.governance, top_k=8)
        self.assertEqual(
            wide_result["valid_actions"], narrow_result["valid_actions"],
            "narrowing the retrieval scope must not change an authorization",
        )
        self.assertTrue(
            any(row.get("predicate") == "workflow_state" for row in narrow_result["assertion_eligible"]),
            "the workflow guard witness must survive eligibility, not merely completion",
        )

    # --- query mode ---------------------------------------------------------

    def test_historical_query_cannot_authorize_an_effectful_action(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = dict(tasks["t_00041"])
        task["retrieval_mode"] = "audit_historical"
        task["audit_time"] = task["decision_time"]
        result = evaluate_lgr(assertions, task, CFG, self.governance, top_k=8)
        self.assertEqual(result["valid_actions"], [])
        for action in result["blocked_actions"]:
            if self.governance.actions.get(action, {}).get("kind") == "effectful":
                self.assertIn("non_authorizing_query_mode", result["blocking_reasons"][action])

    # --- normalization ------------------------------------------------------

    def test_split_mapping_across_variables_is_rejected_not_order_resolved(self) -> None:
        row = assertion("a_split", "Gold", predicate="entitlement_profile", ontology_version="ov_2")
        forward = query(relation_scope=["support_entitlement", "product_entitlement"])
        reverse = query(relation_scope=["product_entitlement", "support_entitlement"])
        # Normalization never consults the query, so the candidate set is
        # identical under either ordering and under an empty scope.
        self.assertEqual(
            normalization_candidates(row, forward, self.governance),
            normalization_candidates(row, reverse, self.governance),
        )
        self.assertEqual(
            normalization_candidates(row, forward, self.governance),
            normalization_candidates(row, query(relation_scope=[]), self.governance),
        )
        self.assertGreater(len(normalization_candidates(row, forward, self.governance)), 1)
        self.assertIsNone(normalized_relation(row, forward, self.governance))
        self.assertIsNone(normalized_relation(row, reverse, self.governance))
        self.assertIn(
            "ontology_ambiguous",
            eligibility_reasons(row, forward, CFG, self.governance, {"a_split": row}),
        )

    def test_renaming_is_resolved_but_a_split_is_not(self) -> None:
        """A pure rename collapses to one variable; a split refuses.

        `refund_status` (ov_1) is a rewrite chain onto `workflow_state`, so it
        must normalize to exactly the same variable the current name does.  A
        split cannot, because no rule in the mapping table says which branch an
        older value meant.
        """
        renamed = assertion("a_renamed", "approved", predicate="refund_status", ontology_version="ov_1")
        current = assertion("a_current", "approved", predicate="workflow_state", ontology_version="ov_3")
        task = query(relation_scope=["workflow_state"])
        self.assertEqual(
            normalized_relation(renamed, task, self.governance),
            normalized_relation(current, task, self.governance),
            "a renamed relation must not hide a conflict behind a second name",
        )
        self.assertEqual(normalized_relation(current, task, self.governance), "workflow_state")

    def test_normalization_is_independent_of_the_querying_scope(self) -> None:
        """The same assertion means the same thing to every query.

        Earlier the fallback branch returned the first target in sort order when
        no query relation matched, so an assertion's identity depended both on
        the query and on how relations happened to be spelled.
        """
        row = assertion("a_iden", "approved", predicate="workflow_state", ontology_version="ov_2")
        scopes = [[], ["workflow_state"], ["sla_profile"], ["sla_profile", "workflow_state"]]
        resolved = {normalized_relation(row, query(relation_scope=s), self.governance) for s in scopes}
        self.assertEqual(resolved, {"workflow_state"})

    # --- provenance and temporal integrity ----------------------------------

    def test_dangling_and_mismatched_provenance_are_rejected(self) -> None:
        dangling = assertion("a_dangling", "active", provenance_activity="pa_not_registered")
        self.assertIn(
            "provenance_unresolved",
            eligibility_reasons(dangling, query(), CFG, self.governance, {"a_dangling": dangling}),
        )
        mismatched = assertion("a_mismatch", "active", provenance_activity="pa_a_00003", source="billing")
        self.assertIn(
            "provenance_source_mismatch",
            eligibility_reasons(mismatched, query(), CFG, self.governance, {"a_mismatch": mismatched}),
        )

    def test_missing_provenance_configuration_fails_closed(self) -> None:
        """An absent or empty registry must reject, not disable the check.

        The check previously ran only when the registry was non-empty, so a
        deployment that had never built one admitted every citation, including
        activities that resolve nowhere.  Missing, empty, and incomplete
        registries are covered separately because they arise differently: an
        empty registry is a truncated artifact, an incomplete one is stale, and
        an absent file is unbuilt (covered at load time by the test below).
        """
        row = assertion("a_prov", "active", provenance_activity="pa_a_00001", source="billing")
        for label, registry in (("empty", {}), ("incomplete", {"pa_other": "billing"})):
            with self.subTest(registry=label):
                self.assertIn(
                    "provenance_unresolved",
                    eligibility_reasons(
                        row, query(), CFG, self.governance, {"a_prov": row}, provenance=registry
                    ),
                    f"a {label} registry resolves nothing for this citation",
                )
        # The same assertion is admissible against the real registry, so the
        # rejections above are caused by the configuration, not the assertion.
        self.assertNotIn(
            "provenance_unresolved",
            eligibility_reasons(row, query(), CFG, self.governance, {"a_prov": row}),
        )

    def test_absent_registry_file_is_rejected_at_load(self) -> None:
        """A missing registry is a misconfiguration, not an empty registry."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            shutil.copytree(DATA, root)
            (root / "generated" / "provenance_activities.jsonl").unlink()
            with self.assertRaises(ValueError) as caught:
                GovernanceBundle.load(root)
            self.assertIn("provenance", str(caught.exception).lower())

    def test_malformed_temporal_fields_do_not_read_as_open_boundaries(self) -> None:
        for field, value in (
            ("valid_until", "not-a-date"),
            ("record_time", "13/05/2026"),
            ("valid_from", "2026-05-01T00:00:00"),
        ):
            row = assertion("a_bad", "active", **{field: value})
            with self.subTest(field=field):
                self.assertIn(
                    "temporal_field_malformed",
                    eligibility_reasons(row, query(), CFG, self.governance, {"a_bad": row}),
                )

    # --- replayable decision record ----------------------------------------

    def test_decision_record_is_deterministic_and_carries_rule_identities(self) -> None:
        tasks = {row["task_id"]: row for row in read_jsonl(DATA / "generated" / "tasks_smoke.jsonl")}
        assertions = read_jsonl(DATA / "generated" / "assertion_events.jsonl")
        task = tasks["t_00041"]
        first = decision_record(evaluate_lgr(assertions, task, CFG, self.governance, top_k=8))
        second = decision_record(evaluate_lgr(assertions, task, CFG, self.governance, top_k=8))
        self.assertEqual(first, second)
        self.assertNotIn("retrieval_latency_ms", json.dumps(first))
        consulted = first["bindings_consulted"]
        admitted = first["valid_actions"]
        self.assertTrue(admitted)
        for action in admitted:
            self.assertIsNotNone(consulted[action]["selected_policy_rule"])
            self.assertIsNotNone(consulted[action]["selected_workflow_transition"])


if __name__ == "__main__":
    unittest.main()
