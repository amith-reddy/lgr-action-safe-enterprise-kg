#!/usr/bin/env python3
"""Partition the frozen split by evidence-label regime and report separately.

The aggregate eligible-F1 of the frozen pilot mixes two incompatible notions of
a correct evidence set:

  * **decision-time labels** -- every gold-eligible assertion was already
    recorded at the query's decision time, so a decision-time operator can in
    principle return exactly that set; and
  * **retrospective labels** -- at least one gold-eligible assertion was
    recorded *after* the query's decision (or audit) time, so an operator that
    honours record-time visibility is required to withhold it.

Averaging the two produces a number that no single retrieval behaviour can
maximize, so this script reports them apart.  It also reports recall alongside
each non-exposure rate, because a method that returns nothing scores a perfect
non-exposure rate; the pair is what distinguishes withholding stale evidence
from withholding everything.

Read-only.  Writes data/evomem_enterprise/phase3/evidence_regimes.json.
"""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lgr_operator import (  # noqa: E402
    GovernanceBundle,
    covers_entity,
    covers_relation,
    parse_time_lenient,
)

DATA = ROOT / "data" / "evomem_enterprise"
GEN = DATA / "generated"
OUT = DATA / "phase3"

METHODS = [
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


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def query_instant(task: dict):
    if task.get("retrieval_mode") == "audit_historical":
        return parse_time_lenient(task.get("audit_time")) or parse_time_lenient(task["decision_time"])
    return parse_time_lenient(task["decision_time"])


def unsatisfiable_reasons(
    task: dict, gold: dict, assertions: dict[str, dict], governance
) -> list[str]:
    """Why no decision-time operator can return exactly this task's gold set.

    Record-time visibility is necessary but not sufficient: a label is
    satisfiable only if every gold-eligible assertion also passes the remaining
    admission predicates and falls inside the query's declared scope.  Checking
    visibility alone would count as satisfiable a label whose evidence the
    operator is required by its own scope rule to withhold.
    """
    reasons: list[str] = []
    when = query_instant(task)
    for assertion_id in gold.get("eligible_assertion_ids") or []:
        row = assertions.get(assertion_id)
        if row is None:
            reasons.append(f"{assertion_id}:absent")
            continue
        recorded = parse_time_lenient(row.get("record_time"))
        if when is None or recorded is None or recorded > when:
            reasons.append(f"{assertion_id}:recorded_after_query")
        if not covers_relation(row, task, governance):
            reasons.append(f"{assertion_id}:relation_out_of_scope")
        if not covers_entity(row, task):
            reasons.append(f"{assertion_id}:entity_out_of_scope")
    return sorted(set(reasons))


def classify(task: dict, gold: dict, assertions: dict[str, dict], governance=None) -> str:
    """Satisfiable when the gold set is one a decision-time operator may return."""
    if governance is None:
        governance = GovernanceBundle.load(DATA)
    reasons = unsatisfiable_reasons(task, gold, assertions, governance)
    if not reasons:
        return "decision_time"
    if any(r.endswith(":recorded_after_query") or r.endswith(":absent") for r in reasons):
        return "retrospective"
    return "scope_unsatisfiable"


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


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
    tasks = {row["task_id"]: row for row in read_jsonl(GEN / "tasks_test.jsonl")}
    gold = {row["task_id"]: row for row in read_jsonl(GEN / "gold_test.jsonl")}
    assertions = {row["assertion_id"]: row for row in read_jsonl(GEN / "assertion_events.jsonl")}
    per_task = read_jsonl(OUT / "per_task_metrics_test.jsonl")

    governance = GovernanceBundle.load(DATA)
    regime = {tid: classify(tasks[tid], gold[tid], assertions, governance) for tid in tasks}
    diagnostics = {
        tid: unsatisfiable_reasons(tasks[tid], gold[tid], assertions, governance)
        for tid in tasks
        if regime[tid] != "decision_time"
    }
    report: dict = {
        "regime_definition": {
            "decision_time": (
                "every gold-eligible assertion was recorded at or before the query "
                "instant and lies inside the query's declared entity and relation scope, "
                "so the gold set is one a decision-time operator may return"
            ),
            "retrospective": "at least one gold-eligible assertion was recorded after the query instant",
            "scope_unsatisfiable": (
                "every gold-eligible assertion was visible in time, but at least one lies "
                "outside the query's declared scope, so the operator's own scope rule "
                "forbids returning the gold set"
            ),
        },
        "unsatisfiable_reasons": diagnostics,
        "task_counts": {
            "decision_time": sum(1 for v in regime.values() if v == "decision_time"),
            "retrospective": sum(1 for v in regime.values() if v == "retrospective"),
            "scope_unsatisfiable": sum(1 for v in regime.values() if v == "scope_unsatisfiable"),
        },
        "task_types_by_regime": {},
        "methods": {},
    }
    by_type: dict[str, dict[str, int]] = {}
    for tid, value in regime.items():
        bucket = by_type.setdefault(
            tasks[tid]["task_type"],
            {"decision_time": 0, "retrospective": 0, "scope_unsatisfiable": 0},
        )
        bucket[value] += 1
    report["task_types_by_regime"] = by_type

    all_methods = sorted({row["method"] for row in per_task})
    for method in all_methods:
        rows = [r for r in per_task if r["method"] == method]
        entry: dict = {}
        for name in ("decision_time", "retrospective", "scope_unsatisfiable"):
            subset = [r for r in rows if regime.get(r["task_id"]) == name]
            entry[name] = {
                "tasks": len(subset),
                "eligible_f1": mean([r["eligible_f1"] for r in subset]),
                "eligible_precision": mean([r["eligible_precision"] for r in subset]),
                "eligible_recall": mean([r["eligible_recall"] for r in subset]),
                "stale_non_exposure": mean([r["stale_suppression_recall"] for r in subset]),
                "loser_non_exposure": mean([r["contradiction_loser_suppression_recall"] for r in subset]),
                "contradiction_winner_recall": mean([r["contradiction_winner_recall"] for r in subset]),
            }
        entry["all_tasks"] = {
            "tasks": len(rows),
            "eligible_f1": mean([r["eligible_f1"] for r in rows]),
            "eligible_recall": mean([r["eligible_recall"] for r in rows]),
        }
        report["methods"][method] = entry

    # Paired bootstrap restricted to the regime whose labels a decision-time
    # operator can satisfy.  Comparing on the mixed set would compare methods
    # against a target no single behaviour can maximize.
    import random

    rng = random.Random(2026061306)
    samples = 1000
    by_method_task = {m: {} for m in METHODS}
    for row in per_task:
        if row["method"] in by_method_task:
            by_method_task[row["method"]][row["task_id"]] = row
    dt_ids = sorted(tid for tid, value in regime.items() if value == "decision_time")
    intervals = {}
    for metric in ("eligible_f1", "stale_suppression_recall", "contradiction_loser_suppression_recall"):
        means = {
            m: mean([by_method_task[m][t][metric] for t in dt_ids])
            for m in METHODS
            if m != "lifecycle_governed_kg_retrieval"
        }
        best = max(means, key=means.get)
        diffs = []
        for _ in range(samples):
            draw = [rng.choice(dt_ids) for _ in dt_ids]
            lgr = mean([by_method_task["lifecycle_governed_kg_retrieval"][t][metric] for t in draw])
            base = mean([by_method_task[best][t][metric] for t in draw])
            diffs.append(lgr - base)
        diffs.sort()
        intervals[metric] = {
            "best_baseline": best,
            "best_baseline_mean": means[best],
            "lgr_minus_best_baseline_mean": mean(diffs),
            "ci95_low": diffs[int(0.025 * len(diffs))],
            "ci95_high": diffs[int(0.975 * len(diffs))],
            "bootstrap_samples": samples,
            "tasks": len(dt_ids),
            "interval_type": "percentile",
        }
    report["decision_time_bootstrap"] = intervals

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidence_regimes.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps(report["task_counts"], indent=2))
    print()
    header = f"{'method':38} {'DT n':>5} {'DT F1':>7} {'DT rec':>7} {'DT stale':>9} {'RS n':>5} {'RS F1':>7} {'RS rec':>7}"
    print(header)
    for method in all_methods:
        e = report["methods"][method]
        d, r = e["decision_time"], e["retrospective"]
        print(
            f"{method:38} {d['tasks']:5} {d['eligible_f1']:7.3f} {d['eligible_recall']:7.3f} "
            f"{d['stale_non_exposure']:9.3f} {r['tasks']:5} {r['eligible_f1']:7.3f} {r['eligible_recall']:7.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
