#!/usr/bin/env python3
"""Score structured LLM outputs for EvoMem-Enterprise.

Usage:
  python3 scripts/score_evomem_llm_outputs.py \
    --gold data/evomem_enterprise/generated/gold_test.jsonl \
    --tasks data/evomem_enterprise/generated/tasks_test.jsonl \
    --packets data/evomem_enterprise/phase3/context_packets_test.jsonl \
    --pred predictions.jsonl

Each prediction row must contain task_id, method, answer, selected_action,
support_assertion_ids, blocked_action_ids, confidence, and rationale.
Support citations are checked only against the exact matching context packet
identified by `(task_id, method)`. Gold labels are never used as a packet
substitute.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path, allow_invalid: bool = False):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    if allow_invalid:
                        rows.append({"task_id": None, "method": None, "_invalid_json": True, "_line_no": line_no})
                    else:
                        raise
    return rows


def empty_metrics() -> dict:
    return {
        "rows_seen": 0,
        "json_valid_outputs": 0,
        "packets_found": 0,
        "answer_correct": 0,
        "selected_action_valid": 0,
        "selected_action_valid_action_only": 0,
        "action_tasks": 0,
        "invalid_action_action_only": 0,
        "blocked_action_correct_action_only": 0,
        "support_complete_set": 0,
        "hallucinated_support_numer": 0,
        "support_ids_total": 0,
        "token_count_total": 0,
        "retrieval_latency_ms_total": 0.0,
    }


def packet_assertion_ids(packet: dict) -> set[str]:
    ids = set(packet.get("assertion_ids", [])) | set(packet.get("retrieved_assertion_ids", []))
    for field in ["eligible_assertions", "retrieved_assertions"]:
        for item in packet.get(field, []):
            if isinstance(item, str):
                ids.add(item)
            elif isinstance(item, dict) and "assertion_id" in item:
                ids.add(item["assertion_id"])
    return ids


def update_metrics(metrics: dict, pred: dict, task: dict, gold: dict, packet: dict) -> None:
    metrics["json_valid_outputs"] += 1
    metrics["packets_found"] += 1
    if pred.get("answer") == gold.get("answer_class") or pred.get("answer") == gold.get("correct_answer"):
        metrics["answer_correct"] += 1

    selected = pred.get("selected_action")
    valid_actions = set(gold.get("valid_actions", []))
    blocked_actions = set(gold.get("blocked_actions", []))
    candidates = set(task.get("candidate_actions", [])) or (valid_actions | blocked_actions)
    action_task = bool(candidates)
    if action_task:
        metrics["action_tasks"] += 1

    if selected in valid_actions or (selected is None and not valid_actions):
        metrics["selected_action_valid"] += 1
        if action_task:
            metrics["selected_action_valid_action_only"] += 1
    if action_task and (selected in blocked_actions or (selected is not None and selected not in candidates)):
        metrics["invalid_action_action_only"] += 1

    pred_blocked = set(pred.get("blocked_action_ids", []))
    must_block = set(gold.get("acceptable_llm_outputs", {}).get("blocked_action_ids_must_include", []))
    if action_task and must_block.issubset(pred_blocked):
        metrics["blocked_action_correct_action_only"] += 1

    support = set(pred.get("support_assertion_ids", []))
    packet_ids = packet_assertion_ids(packet)
    metrics["support_ids_total"] += len(support)
    metrics["hallucinated_support_numer"] += len([sid for sid in support if sid not in packet_ids])
    support_sets = gold.get("acceptable_llm_outputs", {}).get("required_support_sets", [])
    if any(set(sset).issubset(support) for sset in support_sets):
        metrics["support_complete_set"] += 1

    metrics["token_count_total"] += int(packet.get("token_count_estimate") or 0)
    metrics["retrieval_latency_ms_total"] += float(packet.get("retrieval_latency_ms") or 0.0)


def finalize(metrics: dict) -> dict:
    rows_seen = max(metrics["rows_seen"], 1)
    valid_denom = max(metrics["json_valid_outputs"], 1)
    action_denom = max(metrics["action_tasks"], 1)
    support_denom = max(metrics["support_ids_total"], 1)
    return {
        "tasks_scored": metrics["rows_seen"],
        "json_validity_rate": metrics["json_valid_outputs"] / rows_seen,
        "packets_found_rate": metrics["packets_found"] / rows_seen,
        "answer_accuracy": metrics["answer_correct"] / valid_denom,
        "selected_action_valid_accuracy": metrics["selected_action_valid"] / rows_seen,
        "selected_action_valid_accuracy_action_only": metrics["selected_action_valid_action_only"] / action_denom,
        "invalid_action_rate_action_only": metrics["invalid_action_action_only"] / action_denom,
        "blocked_action_correctness_action_only": metrics["blocked_action_correct_action_only"] / action_denom,
        "support_complete_set_rate": metrics["support_complete_set"] / valid_denom,
        "hallucinated_assertion_rate": metrics["hallucinated_support_numer"] / support_denom,
        "avg_token_count_estimate": metrics["token_count_total"] / valid_denom,
        "avg_retrieval_latency_ms": metrics["retrieval_latency_ms_total"] / valid_denom,
        "action_tasks": metrics["action_tasks"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    parser.add_argument("--pred", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--packets", required=True, help="JSONL context packets with task_id/method and retrieved assertion ids.")
    parser.add_argument("--out", required=False, help="Optional path to write the score report JSON.")
    args = parser.parse_args()

    gold = {row["task_id"]: row for row in load_jsonl(Path(args.gold))}
    tasks = {row["task_id"]: row for row in load_jsonl(Path(args.tasks))}
    packets = {
        (row.get("task_id"), row.get("method")): row
        for row in load_jsonl(Path(args.packets))
    }
    preds = load_jsonl(Path(args.pred), allow_invalid=True)

    overall = empty_metrics()
    by_method = defaultdict(empty_metrics)
    details = []

    for pred in preds:
        overall["rows_seen"] += 1
        method = pred.get("method")
        if method:
            by_method[method]["rows_seen"] += 1

        if pred.get("_invalid_json"):
            details.append({"line_no": pred.get("_line_no"), "error": "invalid_json"})
            continue
        tid = pred.get("task_id")
        if not method:
            details.append({"task_id": tid, "error": "missing_method"})
            continue
        task = tasks.get(tid)
        gold_row = gold.get(tid)
        packet = packets.get((tid, method))
        if not gold_row:
            details.append({"task_id": tid, "method": method, "error": "missing_gold"})
            continue
        if not task:
            details.append({"task_id": tid, "method": method, "error": "missing_task"})
            continue
        if not packet:
            details.append({"task_id": tid, "method": method, "error": "missing_exact_packet"})
            continue

        update_metrics(overall, pred, task, gold_row, packet)
        update_metrics(by_method[method], pred, task, gold_row, packet)
        details.append({"task_id": tid, "method": method, "selected_action": pred.get("selected_action")})

    report = {
        **finalize(overall),
        "metrics_by_method": {method: finalize(metrics) for method, metrics in sorted(by_method.items())},
        "details_count": len(details),
        "error_count": len([d for d in details if "error" in d]),
    }
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
