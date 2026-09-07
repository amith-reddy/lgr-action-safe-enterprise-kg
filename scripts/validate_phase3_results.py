#!/usr/bin/env python3
"""Validate Phase 3 experiment artifacts and exit-gate conditions."""

from __future__ import annotations

import json
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
OUT = DATA / "phase3"

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

ACTION_ONLY_METRICS = {
    "action_exact_match_action_only",
    "llm_selected_action_valid_accuracy_action_only",
}

FORBIDDEN_LLM_TASK_FIELDS = {
    "current_workflow_state",
    "valid_actions",
    "blocked_actions",
    "expected_suppression",
    "stage_labels",
    "canonical_role",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def metric_advantage(errors: list[str], metrics: dict, metric: str, minimum_margin: float = 0.0) -> None:
    lgr = metrics["lifecycle_governed_kg_retrieval"].get(metric)
    comparable_baselines = [
        m
        for m in REQUIRED_METHODS
        if m != "lifecycle_governed_kg_retrieval"
        and (metric in ACTION_ONLY_METRICS or m != "event_sourced_latest_state_action")
    ]
    best_baseline = max(metrics[m].get(metric, 0.0) for m in comparable_baselines)
    if lgr is None:
        fail(errors, f"LGR missing metric {metric}")
    elif lgr < best_baseline + minimum_margin:
        fail(errors, f"LGR does not beat best baseline on {metric}: lgr={lgr}, best_baseline={best_baseline}")


def main(data_root: Path | None = None, output_dir: Path | None = None) -> int:
    global DATA, OUT
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        parser.add_argument("--output-dir", type=Path)
        args = parser.parse_args()
        data_root, output_dir = args.data_root, args.output_dir
    DATA = data_root.resolve()
    OUT = output_dir.resolve() if output_dir else DATA / "phase3"
    errors: list[str] = []
    required_files = [
        OUT / "phase3_config.json",
        OUT / "run_manifest.json",
        OUT / "metrics_test.json",
        OUT / "metrics_by_task_type_test.json",
        OUT / "confidence_intervals_test.json",
        OUT / "main_results_table.md",
        OUT / "ablation_table.md",
        OUT / "context_packets_test.jsonl",
        OUT / "llm_inputs_test.jsonl",
        OUT / "llm_proxy_predictions_test.jsonl",
        OUT / "per_task_metrics_test.jsonl",
        DATA / "schema" / "context_packet.schema.json",
        DATA / "schema" / "llm_output.schema.json",
        ROOT / "scripts" / "run_phase3_experiments.py",
        ROOT / "scripts" / "score_evomem_llm_outputs.py",
    ]
    for path in required_files:
        if not path.exists():
            fail(errors, f"missing required Phase 3 artifact: {path}")

    if errors:
        report = {"status": "fail", "errors": errors}
        (OUT / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    config = load_json(OUT / "phase3_config.json")
    manifest = load_json(OUT / "run_manifest.json")
    context_schema = load_json(DATA / "schema" / "context_packet.schema.json")
    llm_schema = load_json(DATA / "schema" / "llm_output.schema.json")
    metrics = load_json(OUT / "metrics_test.json")
    ci = load_json(OUT / "confidence_intervals_test.json")
    packets = load_jsonl(OUT / "context_packets_test.jsonl")
    llm_inputs = load_jsonl(OUT / "llm_inputs_test.jsonl")
    proxy = load_jsonl(OUT / "llm_proxy_predictions_test.jsonl")

    all_methods = set(REQUIRED_METHODS + ABLATIONS)
    if set(metrics) != all_methods:
        fail(errors, f"metrics methods mismatch: {sorted(set(metrics) ^ all_methods)}")
    if set(config.get("methods", {})) != all_methods:
        fail(errors, "phase3_config does not define all required methods and ablations")
    if not config.get("no_dev_tuning"):
        fail(errors, "phase3_config must declare no_dev_tuning=true")
    if manifest.get("real_llm_runs") is not False:
        fail(errors, "manifest must explicitly state whether real LLM runs were used")
    if context_schema.get("additionalProperties") is not False:
        fail(errors, "context_packet.schema.json must use additionalProperties=false")
    if context_schema.get("properties", {}).get("feature_mask", {}).get("additionalProperties") is not False:
        fail(errors, "context_packet.schema.json must strictly define feature_mask")
    if context_schema.get("properties", {}).get("retrieved_assertions", {}).get("items", {}).get("additionalProperties") is not False:
        fail(errors, "context_packet.schema.json must strictly define retrieved assertions")
    if "method" not in llm_schema.get("required", []):
        fail(errors, "llm_output.schema.json must require method")
    if llm_schema.get("additionalProperties") is not False:
        fail(errors, "llm_output.schema.json must use additionalProperties=false")
    scorer_text = (ROOT / "scripts" / "score_evomem_llm_outputs.py").read_text(encoding="utf-8")
    if "packets_by_task" in scorer_text or "fallback to gold" in scorer_text.lower():
        fail(errors, "LLM scorer must not include task-only packet or gold fallback logic")

    packet_methods = {row.get("method") for row in packets}
    if packet_methods != all_methods:
        fail(errors, f"context packets do not cover all methods: {sorted(packet_methods ^ all_methods)}")
    if {row.get("method") for row in proxy} != all_methods:
        fail(errors, "proxy predictions do not cover all methods")

    for packet in packets[:]:
        if packet.get("feature_mask", {}).get("oracle_fields_visible") is not False:
            fail(errors, f"packet exposes oracle fields: {packet.get('packet_id')}")
        ids = packet.get("retrieved_assertion_ids", [])
        row_ids = [a.get("assertion_id") for a in packet.get("retrieved_assertions", [])]
        if ids != row_ids:
            fail(errors, f"packet id list does not match assertion rows: {packet.get('packet_id')}")
        for assertion in packet.get("retrieved_assertions", []):
            if "canonical_role" in assertion:
                fail(errors, f"canonical_role leaked into packet: {packet.get('packet_id')}")
            if packet["method"] == "lgr_no_lifecycle_state" and "lifecycle_state" in assertion:
                fail(errors, f"lifecycle ablation leaks lifecycle_state: {packet.get('packet_id')}")

    for item in llm_inputs:
        task_view = item.get("task_view", {})
        leaked = sorted(FORBIDDEN_LLM_TASK_FIELDS & set(task_view))
        if leaked:
            fail(errors, f"LLM input leaks forbidden task fields {leaked}: {item.get('packet_id')}")
        text = json.dumps(item)
        for forbidden in ["canonical_role", "expected_suppression", "stage_labels"]:
            if forbidden in text:
                fail(errors, f"LLM input leaks {forbidden}: {item.get('packet_id')}")

    lgr = metrics["lifecycle_governed_kg_retrieval"]
    test_tasks = load_jsonl(DATA / "generated" / "tasks_test.jsonl")
    expected_action_tasks = sum(1 for task in test_tasks if task.get("candidate_actions"))
    if lgr.get("action_tasks") != expected_action_tasks:
        fail(errors, f"expected {expected_action_tasks} test action tasks from the frozen split, found {lgr.get('action_tasks')}")
    for metric in [
        "eligible_f1",
        "stale_suppression_recall",
        "contradiction_loser_suppression_recall",
    ]:
        metric_advantage(errors, metrics, metric)
        if metric not in ci:
            fail(errors, f"missing bootstrap CI for {metric}")

    # Action admission is intentionally evaluated over the shared decision
    # closure; action equality is a conformance check, not a retrieval win.
    for method in REQUIRED_METHODS:
        if metrics[method].get("action_exact_match_action_only") != lgr.get("action_exact_match_action_only"):
            fail(errors, f"common action gate diverges for {method}")
    for packet in packets:
        if packet.get("decision_evidence_status") != "complete_for_declared_snapshot":
            fail(errors, f"incomplete decision evidence: {packet.get('packet_id')}")
        if packet.get("initial_retrieval_budget") != 8:
            fail(errors, f"unexpected initial retrieval budget: {packet.get('packet_id')}")

    if lgr.get("llm_invalid_action_rate_action_only", 1.0) >= 0.10:
        fail(errors, "LGR invalid-action rate must stay below 10% in proxy action-only evaluation")
    if lgr.get("hallucinated_assertion_rate", 1.0) != 0.0:
        fail(errors, "LGR proxy must not hallucinate assertion ids")

    report = {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "required_methods": REQUIRED_METHODS,
        "ablations": ABLATIONS,
        "lgr_test_metrics": lgr,
        "confidence_intervals": ci,
    }
    (OUT / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
