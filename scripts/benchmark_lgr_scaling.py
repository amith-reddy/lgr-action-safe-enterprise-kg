#!/usr/bin/env python3
"""Measure the reference LGR implementation as graph and query neighborhoods grow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lgr_operator import GovernanceBundle, admit_actions, decision_evidence_completion, eligibility_reasons, evaluate_lgr, resolve_conflicts
from run_phase3_experiments import method_config

DEFAULT_DATA = ROOT / "data" / "evomem_enterprise"
DEFAULT_OUTPUT = ROOT / "experiments" / "lgr_jws" / "scaling" / "scaling_report.json"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def clone(row: dict, index: int, *, dense: bool, task: dict) -> dict:
    copy = json.loads(json.dumps(row))
    prefix = f"scale_{index:07d}"
    copy["assertion_id"] = prefix
    copy["supersedes"] = []
    copy["superseded_by"] = []
    copy["contradiction_group"] = None
    if dense:
        copy["subject"] = task["entity_scope"][0]
        copy["entity_scope"] = list(task["entity_scope"])
        copy["workflow_instance_id"] = None
    else:
        old_subject = str(copy.get("subject") or "subject")
        copy["subject"] = f"unrelated_{index}_{old_subject}"
        copy["entity_scope"] = [copy["subject"]]
        if copy.get("workflow_instance_id"):
            copy["workflow_instance_id"] = f"unrelated_workflow_{index}"
    return copy


def expand(base: list[dict], size: int, mode: str, task: dict) -> list[dict]:
    result = json.loads(json.dumps(base))
    dense_sources = [row for row in base if row.get("predicate") in set(task.get("relation_scope") or []) and row.get("source") and row.get("provenance_activity")]
    sources = dense_sources if mode == "dense" and dense_sources else base
    index = 0
    while len(result) < size:
        result.append(clone(sources[index % len(sources)], index, dense=mode == "dense", task=task))
        index += 1
    return result[:size]


def timed_once(assertions, task, governance, cfg):
    begin = time.perf_counter_ns()
    evidence, _ = decision_evidence_completion(assertions, task, governance)
    after_completion = time.perf_counter_ns()
    index = {row["assertion_id"]: row for row in assertions}
    eligible = [row for row in evidence if not eligibility_reasons(row, task, cfg, governance, index)]
    after_eligibility = time.perf_counter_ns()
    resolved, _, unresolved, _ = resolve_conflicts(eligible, task, governance, enabled=True)
    after_conflict = time.perf_counter_ns()
    admission = admit_actions(resolved, task, governance, unresolved, enforce_binding=True)
    after_admission = time.perf_counter_ns()
    evaluate_lgr(assertions, task, cfg, governance, top_k=8)
    after_total = time.perf_counter_ns()
    return {
        "completion_ms": (after_completion - begin) / 1e6,
        "eligibility_ms": (after_eligibility - after_completion) / 1e6,
        "conflict_ms": (after_conflict - after_eligibility) / 1e6,
        "admission_ms": (after_admission - after_conflict) / 1e6,
        "instrumented_stage_total_ms": (after_admission - begin) / 1e6,
        "independent_end_to_end_ms": (after_total - after_admission) / 1e6,
        "candidate_closure_size": len(evidence),
        "eligible_size": len(eligible),
        "resolved_size": len(resolved),
        "valid_actions": len(admission["valid_actions"]),
    }


def quantile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 100000])
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument(
        "--dense-warmups",
        type=int,
        default=3,
        help="Warm-up runs for dense candidate neighborhoods (default: 3).",
    )
    parser.add_argument(
        "--dense-samples",
        type=int,
        default=30,
        help="Measured runs for dense candidate neighborhoods (default: 30).",
    )
    args = parser.parse_args()
    data = args.data_root.resolve()
    base = read_jsonl(data / "generated" / "assertion_events.jsonl")
    task = next(row for row in read_jsonl(data / "generated" / "tasks_test.jsonl") if row.get("candidate_actions"))
    governance = GovernanceBundle.load(data)
    cfg = method_config("lifecycle_governed_kg_retrieval")
    raw, summaries = [], []
    for mode in ("unrelated_growth", "dense"):
        for size in args.sizes:
            warmups = args.dense_warmups if mode == "dense" else args.warmups
            sample_count = args.dense_samples if mode == "dense" else args.samples
            print(
                f"measuring mode={mode} assertions={size} warmups={warmups} samples={sample_count}",
                file=sys.stderr,
                flush=True,
            )
            assertions = expand(base, size, "dense" if mode == "dense" else "unrelated", task)
            serialization_begin = time.perf_counter_ns()
            serialized = json.dumps(assertions, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(serialized).hexdigest()
            serialization_ms = (time.perf_counter_ns() - serialization_begin) / 1e6
            for _ in range(warmups):
                timed_once(assertions, task, governance, cfg)
            measurements = []
            for sample in range(sample_count):
                row = timed_once(assertions, task, governance, cfg)
                row.update({"mode": mode, "assertions": size, "sample": sample})
                raw.append(row); measurements.append(row)
            metrics = {}
            for name in ("completion_ms", "eligibility_ms", "conflict_ms", "admission_ms", "instrumented_stage_total_ms", "independent_end_to_end_ms"):
                values = [row[name] for row in measurements]
                metrics[name] = {"p50": statistics.median(values), "p95": quantile(values, .95), "mean": statistics.mean(values)}
            summaries.append({
                "mode": mode, "assertions": size, "samples": sample_count, "warmups": warmups,
                "serialized_bytes": len(serialized), "snapshot_digest_ms": serialization_ms,
                "semantic_sha256": digest, "closure_size": measurements[0]["candidate_closure_size"],
                "metrics": metrics,
            })
    report = {
        "status": "pass", "implementation": "Python reference implementation",
        "index_construction": "No persistent retrieval index is used by this implementation.",
        "hardware": {"platform": platform.platform(), "python": sys.version, "logical_cpus": os.cpu_count(), "peak_rss_process_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "task_id": task["task_id"], "summaries": summaries, "raw": raw,
        "limitations": ["Synthetic replicas preserve source schema and do not model an operational storage engine.", "Peak RSS is process-wide and reported in the operating system's native ru_maxrss units."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "output": str(args.output), "runs": len(raw), "summaries": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
