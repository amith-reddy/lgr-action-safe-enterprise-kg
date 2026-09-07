#!/usr/bin/env python3
"""Decisive-stratum and masking diagnostics for the zero-effect ablations.

The frozen pilot reports no aggregate metric change for the lifecycle,
ontology-version, policy-version, and supersession ablations.  This script
makes the reason executable rather than conjectural:

Part A (masking audit, read-only over the frozen split) recomputes, with the
released operator, every eligibility failure over each test task's completed
decision evidence and reports, per governance feature, how often the feature's
predicate fired alone versus together with another predicate.  It also checks
the structural claim that an ontology-normalization failure always co-occurs
with a relation-scope failure, so the ontology-version ablation flag cannot
change eligibility membership on any split.

Part B (decisive counterfactual strata) evaluates small, self-contained
worlds in which exactly one predicate decides eligibility.  Each stratum is
run under the full operator and under the matching ablation; the script
verifies that the full operator excludes the target assertion for exactly the
intended sole reason, that the ablated operator exposes it, and, where a
stratum is constructed to be action-decisive, that the ablated operator
admits an effectful action the full operator blocks.

The script fails (nonzero exit) if any decisive expectation does not hold.
Output: data/evomem_enterprise/phase3/decisive_strata_report.json
"""

from __future__ import annotations

import json
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lgr_operator import (  # noqa: E402
    GovernanceBundle,
    decision_evidence_completion,
    eligibility_reasons,
    evaluate_lgr,
)

DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"
OUT = DATA / "phase3"

FULL_CFG = {
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

FEATURE_REASONS = {
    "lifecycle_state": "lifecycle_ineligible",
    "ontology_versioning": "ontology_incompatible",
    "policy_versioning": "policy_version_incompatible",
    "supersession_links": "superseded",
}

FEATURE_FLAGS = {
    "lifecycle_state": "use_lifecycle_state",
    "ontology_versioning": "use_ontology_versioning",
    "policy_versioning": "use_policy_versioning",
    "supersession_links": "use_supersession_links",
}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def ablated(feature: str) -> dict:
    cfg = dict(FULL_CFG)
    cfg[FEATURE_FLAGS[feature]] = False
    return cfg


def masking_audit(governance: GovernanceBundle) -> dict:
    """Reason co-occurrence over completed decision evidence on the frozen split."""
    tasks = load_jsonl(GEN / "tasks_test.jsonl")
    assertions = load_jsonl(GEN / "assertion_events.jsonl")
    assertion_index = {row["assertion_id"]: row for row in assertions}
    stats = {
        feature: {"instances": 0, "sole": 0, "co_occurring": 0, "partners": Counter()}
        for feature in FEATURE_REASONS
    }
    ontology_pairs = 0
    ontology_without_scope = 0
    eligibility_membership_diffs = {feature: 0 for feature in FEATURE_REASONS}
    for task in tasks:
        evidence, _ = decision_evidence_completion(assertions, task, governance)
        for row in evidence:
            reasons = set(eligibility_reasons(row, task, FULL_CFG, governance, assertion_index))
            for feature, reason in FEATURE_REASONS.items():
                if reason not in reasons:
                    continue
                bucket = stats[feature]
                bucket["instances"] += 1
                others = reasons - {reason}
                if others:
                    bucket["co_occurring"] += 1
                    for other in sorted(others):
                        bucket["partners"][other] += 1
                else:
                    bucket["sole"] += 1
            # Membership check: does disabling the flag change eligibility?
            for feature in FEATURE_REASONS:
                full_eligible = not reasons
                ablated_reasons = set(
                    eligibility_reasons(row, task, ablated(feature), governance, assertion_index)
                )
                if full_eligible != (not ablated_reasons):
                    eligibility_membership_diffs[feature] += 1
        # Structural shadowing check over the full corpus for this task.
        for row in assertions:
            reasons = set(eligibility_reasons(row, task, FULL_CFG, governance, assertion_index))
            if "ontology_incompatible" in reasons:
                ontology_pairs += 1
                if "scope_relation_mismatch" not in reasons:
                    ontology_without_scope += 1
    report = {
        feature: {
            "instances": bucket["instances"],
            "sole_reason": bucket["sole"],
            "co_occurring": bucket["co_occurring"],
            "partners": dict(bucket["partners"].most_common()),
        }
        for feature, bucket in stats.items()
    }
    report["ontology_structural_shadowing"] = {
        "corpus_pairs_with_ontology_incompatible": ontology_pairs,
        "pairs_missing_scope_relation_mismatch": ontology_without_scope,
        "implication_holds": ontology_without_scope == 0,
    }
    report["eligibility_membership_changes_on_completed_evidence"] = eligibility_membership_diffs
    return report


# Each stratum must isolate one predicate, so every fixture cites a provenance
# activity that the declared registry actually attributes to its own source;
# otherwise ProvOK would co-fire and the stratum would no longer be decisive.
REGISTERED_ACTIVITY = {
    "billing": "pa_a_00001",
    "support_note": "pa_a_00003",
    "crm": "pa_a_00005",
    "workflow_log": "pa_a_00009",
    "policy_registry": "pa_a_00421",
}


def fixture(assertion_id: str, **overrides) -> dict:
    row = {
        "assertion_id": assertion_id,
        "subject": "acct_001",
        "predicate": "subscription_status",
        "object": "active",
        "assertion_type": "semantic_fact",
        "entity_scope": ["acct_001"],
        "event_time": "2026-05-01T00:00:00Z",
        "record_time": "2026-05-01T00:05:00Z",
        "valid_from": "2026-05-01T00:00:00Z",
        "valid_until": None,
        "ontology_version": "ov_3",
        "policy_version": "refund_policy_v2",
        "source": "billing",
        "lifecycle_state": "active",
        "supersedes": [],
        "superseded_by": [],
        "workflow_instance_id": None,
    }
    row.update(overrides)
    row.setdefault("provenance_activity", REGISTERED_ACTIVITY[row["source"]])
    if "provenance_activity" not in overrides:
        row["provenance_activity"] = REGISTERED_ACTIVITY[row["source"]]
    return row


def fixture_query(**overrides) -> dict:
    row = {
        "task_id": "decisive",
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


def decisive_cases() -> dict[str, list[dict]]:
    """Self-contained worlds where exactly one predicate decides eligibility."""
    cases: dict[str, list[dict]] = defaultdict(list)

    # Lifecycle: retraction without replacement (a compliance takedown).  The
    # record stays within its validity interval, keeps provenance and version
    # compatibility, and has no supersession link, so only LifeOK excludes it.
    for idx, (predicate, value, source) in enumerate(
        [
            ("subscription_status", "active", "billing"),
            ("support_entitlement", "Premium", "billing"),
            ("sla_profile", "Premium", "billing"),
        ]
    ):
        target = fixture(
            f"lc_{idx}", predicate=predicate, object=value, source=source,
            lifecycle_state="retracted",
        )
        cases["lifecycle_state"].append(
            {
                "case_id": f"lifecycle_takedown_{idx}",
                "world": [target],
                "query": fixture_query(relation_scope=[predicate]),
                "target": target["assertion_id"],
                "expected_sole_reason": "lifecycle_ineligible",
            }
        )
    # Lifecycle action flip: a retracted approval record is the only workflow
    # witness.  The full operator blocks issue_refund for lack of a witness;
    # the ablated operator admits it on retracted evidence.
    wf_state = fixture(
        "lc_wf", subject="wf_9001", predicate="workflow_state", object="approved",
        source="workflow_log", lifecycle_state="retracted",
        entity_scope=["acct_001"], workflow_instance_id="wf_9001",
    )
    sub_ok = fixture("lc_sub", object="active")
    cases["lifecycle_state"].append(
        {
            "case_id": "lifecycle_action_flip",
            "world": [wf_state, sub_ok],
            "query": fixture_query(
                relation_scope=["workflow_state", "subscription_status"],
                candidate_actions=["issue_refund"],
                workflow_instance_id="wf_9001",
            ),
            "target": wf_state["assertion_id"],
            "expected_sole_reason": "lifecycle_ineligible",
            "action_flip": "issue_refund",
        }
    )

    # Supersession: an explicit replacement recorded by a source lower in the
    # static authority order than the record it replaces.  The predecessor
    # stays active and within validity, so only SupOK excludes it; without
    # supersession the predecessor also wins the authority-ordered resolver,
    # so no other stage masks the removal.
    for idx, (predicate, old, new, high, low) in enumerate(
        [
            ("subscription_status", "active", "cancelled", "billing", "crm"),
            ("support_entitlement", "Premium", "Standard", "billing", "crm"),
        ]
    ):
        pred = fixture(
            f"sp_{idx}_old", predicate=predicate, object=old, source=high,
            superseded_by=[f"sp_{idx}_new"],
        )
        succ = fixture(
            f"sp_{idx}_new", predicate=predicate, object=new, source=low,
            record_time="2026-05-10T00:05:00Z", valid_from="2026-05-10T00:00:00Z",
            supersedes=[f"sp_{idx}_old"],
        )
        cases["supersession_links"].append(
            {
                "case_id": f"supersession_lagging_close_{idx}",
                "world": [pred, succ],
                "query": fixture_query(relation_scope=[predicate]),
                "target": pred["assertion_id"],
                "expected_sole_reason": "superseded",
            }
        )
    # Supersession action flip: the workflow log wrote "approved"; an explicit
    # replacement from a lower-authority channel later recorded "rejected".
    wf_old = fixture(
        "sp_wf_old", subject="wf_9002", predicate="workflow_state", object="approved",
        source="workflow_log", entity_scope=["acct_001"],
        workflow_instance_id="wf_9002", superseded_by=["sp_wf_new"],
    )
    wf_new = fixture(
        "sp_wf_new", subject="wf_9002", predicate="workflow_state", object="rejected",
        source="support_note", entity_scope=["acct_001"],
        workflow_instance_id="wf_9002", record_time="2026-05-12T00:05:00Z",
        valid_from="2026-05-12T00:00:00Z", supersedes=["sp_wf_old"],
    )
    sub_ok2 = fixture("sp_sub", object="active")
    cases["supersession_links"].append(
        {
            "case_id": "supersession_action_flip",
            "world": [wf_old, wf_new, sub_ok2],
            "query": fixture_query(
                relation_scope=["workflow_state", "subscription_status"],
                candidate_actions=["issue_refund"],
                workflow_instance_id="wf_9002",
            ),
            "target": wf_old["assertion_id"],
            "expected_sole_reason": "superseded",
            "action_flip": "issue_refund",
        }
    )

    # Policy version: a governance fact from the previous policy regime whose
    # validity interval was never closed.  Only PolicyVerOK excludes it.  The
    # ablated operator exposes the wrong-regime rule text to the packet; the
    # action gate reads the versioned policy table, so admission must not
    # change, which the harness also verifies.
    for idx, (predicate, value, version) in enumerate(
        [
            ("refund_rule", "refund_within_90_days", "refund_policy_v1"),
            ("refund_rule", "refund_requires_receipt_only", "refund_policy_v1"),
            ("sla_rule", "response_within_48h", "refund_policy_v1"),
        ]
    ):
        target = fixture(
            f"pv_{idx}", predicate=predicate, object=value, source="policy_registry",
            assertion_type="policy_fact", policy_version=version,
        )
        cases["policy_versioning"].append(
            {
                "case_id": f"policy_regime_unclosed_validity_{idx}",
                "world": [target],
                "query": fixture_query(relation_scope=[predicate]),
                "target": target["assertion_id"],
                "expected_sole_reason": "policy_version_incompatible",
                "gate_must_not_change": True,
            }
        )
    return cases


def run_decisive(governance: GovernanceBundle) -> tuple[dict, list[str]]:
    failures: list[str] = []
    strata = []
    for feature, cases in decisive_cases().items():
        stratum = {
            "feature": feature,
            "tasks": len(cases),
            "full_lgr_exposures": 0,
            "ablated_exposures": 0,
            "action_flips_expected": sum(1 for case in cases if case.get("action_flip")),
            "action_flips_observed": 0,
            "cases": [],
        }
        for case in cases:
            world, task = case["world"], case["query"]
            index = {row["assertion_id"]: row for row in world}
            sole = eligibility_reasons(index[case["target"]], task, FULL_CFG, governance, index)
            if sole != [case["expected_sole_reason"]]:
                failures.append(
                    f"{case['case_id']}: expected sole reason {case['expected_sole_reason']!r}, got {sole!r}"
                )
            full = evaluate_lgr(world, task, FULL_CFG, governance, top_k=8)
            abl = evaluate_lgr(world, task, ablated(feature), governance, top_k=8)
            full_ids = {row["assertion_id"] for row in full["packet_assertions"]}
            abl_ids = {row["assertion_id"] for row in abl["packet_assertions"]}
            exposed_full = case["target"] in full_ids
            exposed_abl = case["target"] in abl_ids
            stratum["full_lgr_exposures"] += int(exposed_full)
            stratum["ablated_exposures"] += int(exposed_abl)
            if exposed_full:
                failures.append(f"{case['case_id']}: full operator exposed the target assertion")
            if not exposed_abl:
                failures.append(f"{case['case_id']}: ablated operator did not expose the target")
            flip = case.get("action_flip")
            if flip:
                if flip in full["valid_actions"]:
                    failures.append(f"{case['case_id']}: full operator admitted {flip}")
                if flip in abl["valid_actions"]:
                    stratum["action_flips_observed"] += 1
                else:
                    failures.append(f"{case['case_id']}: ablated operator did not admit {flip}")
            if case.get("gate_must_not_change") and (
                full["valid_actions"] != abl["valid_actions"]
                or full["blocked_actions"] != abl["blocked_actions"]
            ):
                failures.append(f"{case['case_id']}: gate outcome changed under policy-version ablation")
            stratum["cases"].append(
                {
                    "case_id": case["case_id"],
                    "sole_reason": sole,
                    "exposed_full": exposed_full,
                    "exposed_ablated": exposed_abl,
                    "full_valid_actions": full["valid_actions"],
                    "ablated_valid_actions": abl["valid_actions"],
                }
            )
        strata.append(stratum)
    return {"strata": strata}, failures


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
    governance = GovernanceBundle.load(DATA)
    masking = masking_audit(governance)
    decisive, failures = run_decisive(governance)
    report = {
        "frozen_split_masking": masking,
        "decisive_counterfactual_strata": decisive["strata"],
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "decisive_strata_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
