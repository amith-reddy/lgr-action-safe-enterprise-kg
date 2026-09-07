#!/usr/bin/env python3
"""Run the executable LGR conformance suite and seal a JSON report."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lgr_operator import snapshot_manifest  # noqa: E402


DATA = ROOT / "data" / "evomem_enterprise"
OUT = DATA / "phase3" / "conformance_report.json"


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_lgr_conformance")
    result = unittest.TestResult()
    suite.run(result)
    label_report = json.loads(
        (DATA / "validation" / "gold_action_conformance_report.json").read_text(encoding="utf-8")
    )
    verifier = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_gold_labels.py")],
        capture_output=True,
        text=True,
    )
    verifier_report = json.loads(verifier.stdout) if verifier.stdout.strip() else {"status": "error"}
    evidence_verifier = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_evidence_labels.py")],
        capture_output=True,
        text=True,
    )
    evidence_report = (
        json.loads(evidence_verifier.stdout) if evidence_verifier.stdout.strip() else {"status": "error"}
    )
    report = {
        "suite": "lgr-formal-conformance-v1",
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests_run": result.testsRun,
        "failures": [{"test": str(test), "message": message} for test, message in result.failures],
        "errors": [{"test": str(test), "message": message} for test, message in result.errors],
        "coverage": [
            "eight eligibility predicates, including record-time visibility and validity boundaries",
            "source membership in a declared relation-specific trust order",
            "permanent supersession by a visible successor, future-successor visibility, and invalid-link rejection",
            "relation-specific conflict keys, multi-value coexistence, descending record-time resolution",
            "explicit unresolved equal-authority tie",
            "authoritative decision-evidence completion for action-guard dependencies",
            "trust-table duplicate, relation, relation/source-pair, and version failures",
            "registered default-deny action admission",
            "registered advisory action admission without effectful bindings",
            "effectful action policy-family isolation",
            "equal-or-higher-priority policy deny precedence",
            "policy/workflow witness-carrying admission",
            "deterministic packet replay",
            "snapshot mutation detection",
            "guard witnesses bound to one action target; unrelated entities cannot authorize",
            "action targets resolved from declared workflow membership, never from identifier spelling",
            "colliding identifier suffixes and renamed case identifiers do not alter membership",
            "only the workflow's own trusted records may declare case participants",
            "ambiguous action binding refused rather than evaluated against a mixture",
            "declared guard dependencies survive eligibility under a narrowed retrieval scope",
            "historical and investigation queries cannot authorize an effectful action",
            "cross-variable split mappings rejected instead of resolved by scope or sort order",
            "renamed relations normalize to one canonical decision variable",
            "normalization independent of the querying relation scope",
            "dangling and source-mismatched provenance references rejected",
            "empty and incomplete provenance registries fail closed; an absent registry is rejected at load",
            "malformed temporal fields rejected rather than read as open boundaries",
            "deterministic decision record excludes retrieval context and runtime measurements",
            "selected policy rule and workflow transition identities recorded",
        ],
        "snapshot": snapshot_manifest(DATA),
        "label_verification": {
            "checker": verifier_report.get("checker"),
            "status": verifier_report.get("status"),
            "action_labels_checked": verifier_report.get("action_labels_checked"),
            "disagreements": len(verifier_report.get("disagreements") or []),
            "writes_to_benchmark": verifier_report.get("writes_to_benchmark"),
            "note": "validation-only: re-derives frozen labels from the tables and fails on disagreement",
        },
        "evidence_label_verification": {
            "checker": evidence_report.get("checker"),
            "status": evidence_report.get("status"),
            "test_task_regimes": evidence_report.get("test_task_regimes"),
            "permitted_label_failures": len(evidence_report.get("permitted_label_failures") or []),
            "writes_to_benchmark": evidence_report.get("writes_to_benchmark"),
            "note": "validation-only: independently checks eligibility and conflict resolution",
        },
        "action_label_cross_check": {
            "independent_interpreter": label_report.get("oracle"),
            "imports_evaluated_operator": label_report.get("imports_evaluated_operator"),
            "action_labels_table_conformant": label_report.get("action_labels_table_conformant"),
            "labels_rewritten_by_generation_step": label_report.get("action_label_disagreements"),
            "evidence_sets_written_by_generation_step": len(label_report.get("evidence_changes", [])),
            "task_states_written_by_generation_step": len(label_report.get("task_state_changes", [])),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    # The combined gate passes only when both components pass.  Reporting the
    # verifier's status while deriving the exit code from the unit tests alone
    # would let a label disagreement leave the gate green.
    # `action_label_disagreements` in the re-derivation report counts labels that
    # run rewrote, so it is a record of that run rather than a live check; the
    # validation-only verifier is what independently re-checks the frozen labels.
    verifier_ok = verifier_report.get("status") == "pass" and not (
        verifier_report.get("disagreements") or []
    )
    evidence_ok = evidence_report.get("status") == "pass" and not (
        evidence_report.get("permitted_label_failures") or []
    )
    return 0 if (result.wasSuccessful() and verifier_ok and evidence_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
