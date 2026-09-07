#!/usr/bin/env python3
"""Generate, validate, and summarize the pre-specified JWS multiworld study."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "experiments" / "lgr_jws" / "protocol.json"
DEFAULT_OUTPUT = ROOT / "data" / "evomem_enterprise_v3" / "worlds"
BASELINES = [
    "lexical_top_k_memory", "recency_weighted_memory", "ttl_only_memory",
    "temporal_kg_retrieval", "provenance_aware_kg_query",
    "ontology_versioned_retrieval", "graphrag_style_graph_retrieval",
    "event_sourced_latest_state_action",
]
LGR = "lifecycle_governed_kg_retrieval"


def run(script: str, *args: str) -> str:
    command = [sys.executable, str(ROOT / "scripts" / script), *args]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result.stdout


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(p * len(ordered))))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true", help="reuse already generated world artifacts and rerun validation/summary")
    parser.add_argument("--rerun-evaluation", action="store_true", help="with --resume, regenerate Phase 3 outputs without regenerating worlds")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()) and not args.resume:
        if not args.force:
            raise SystemExit(f"refusing to overwrite nonempty multiworld directory: {output}; pass --force")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    records, failures = [], []
    for role, seeds in protocol["worlds"].items():
        for index, seed in enumerate(seeds, 1):
            world_id = f"{role}-{index:02d}-s{seed}"
            world = output / world_id
            try:
                if not (args.resume and (world / "phase3" / "metrics_test.json").exists()):
                    run("generate_evomem_enterprise.py", "--output-dir", str(world), "--master-seed", str(seed), "--world-id", world_id, "--benchmark-version", protocol["generator_version"])
                    run("build_provenance_registry.py", "--data-root", str(world))
                    run("validate_evomem_enterprise.py", "--data-root", str(world))
                    run("rederive_evomem_gold.py", "--data-root", str(world))
                    run("run_phase3_experiments.py", "--data-root", str(world))
                    run("report_evidence_regimes.py", "--data-root", str(world))
                elif args.rerun_evaluation:
                    shutil.copy2(
                        ROOT / "data" / "evomem_enterprise" / "schema" / "context_packet.schema.json",
                        world / "schema" / "context_packet.schema.json",
                    )
                    run("run_phase3_experiments.py", "--data-root", str(world))
                    run("report_evidence_regimes.py", "--data-root", str(world))
                run("verify_gold_labels.py", "--data-root", str(world))
                evidence_stdout = run("verify_evidence_labels.py", "--data-root", str(world))
                evidence = json.loads(evidence_stdout)
                run("validate_phase3_results.py", "--data-root", str(world))
                run("run_decisive_strata.py", "--data-root", str(world))
                run("composed_governance_baseline.py", "--data-root", str(world))
                regime = json.loads((world / "phase3" / "evidence_regimes.json").read_text())
                composed = json.loads((world / "phase3" / "composed_governance_report.json").read_text())
                row = {
                    "role": role,
                    "world_id": world_id,
                    "master_seed": seed,
                    "task_counts": evidence["test_task_regimes"],
                    "methods": {
                        method: regime["methods"][method]["decision_time"]
                        for method in BASELINES + [LGR]
                    },
                    "composed_governance": {
                        "evidence_equal_to_lgr": composed["evidence_equal_to_lgr"],
                        "test_tasks": composed["test_tasks"],
                        "action_equal_to_gold": composed["action_equal_to_gold"],
                        "action_tasks": composed["action_tasks"],
                    },
                }
                records.append(row)
            except Exception as exc:
                failures.append({"role": role, "world_id": world_id, "master_seed": seed, "error": str(exc)})

    (output / "world_metrics.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    (output / "failures.json").write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
    if failures:
        print(json.dumps({"status": "fail", "failures": failures}, indent=2))
        return 1

    validation = [row for row in records if row["role"] == "validation"]
    validation_means = {
        method: statistics.mean(row["methods"][method]["eligible_f1"] for row in validation)
        for method in BASELINES
    }
    comparator = max(validation_means, key=validation_means.get)
    test = [row for row in records if row["role"] == "test"]
    differences = [row["methods"][LGR]["eligible_f1"] - row["methods"][comparator]["eligible_f1"] for row in test]
    rng = random.Random(protocol["uncertainty"]["bootstrap_seed"])
    samples = []
    for _ in range(protocol["uncertainty"]["bootstrap_samples"]):
        samples.append(statistics.mean(rng.choice(differences) for _ in differences))
    metric_summary = {}
    for method in BASELINES + [LGR]:
        metric_summary[method] = {}
        for metric in ("eligible_f1", "eligible_recall", "stale_non_exposure", "loser_non_exposure"):
            values = [row["methods"][method][metric] for row in test]
            metric_summary[method][metric] = {
                "mean": statistics.mean(values),
                "sample_sd": statistics.stdev(values) if len(values) > 1 else 0.0,
                "world_values": values,
            }
    summary = {
        "status": "pass",
        "protocol_version": protocol["protocol_version"],
        "worlds": {role: len(seeds) for role, seeds in protocol["worlds"].items()},
        "primary_population_total_test_tasks": sum(row["task_counts"]["permitted"] for row in test),
        "primary_comparator": comparator,
        "validation_baseline_means": validation_means,
        "test_metrics": metric_summary,
        "paired_test_difference": {
            "metric": "eligible_f1",
            "lgr_minus_comparator_mean": statistics.mean(differences),
            "ci95_low": percentile(samples, 0.025),
            "ci95_high": percentile(samples, 0.975),
            "bootstrap_unit": "world",
            "bootstrap_samples": len(samples),
            "per_world_differences": differences,
        },
        "composed_governance_conformance": {
            "evidence_equal_to_lgr": sum(row["composed_governance"]["evidence_equal_to_lgr"] for row in records),
            "evidence_tasks": sum(row["composed_governance"]["test_tasks"] for row in records),
            "action_equal_to_gold": sum(row["composed_governance"]["action_equal_to_gold"] for row in records),
            "action_tasks": sum(row["composed_governance"]["action_tasks"] for row in records),
            "scope": "all development, validation, and test worlds",
        },
        "limitations": [
            "All worlds share one generator family and scenario assumptions.",
            "The number of worlds is an engineering budget rather than a prospective power calculation.",
            "Retrospective and out-of-scope labels are retained as diagnostics and excluded from the primary population."
        ],
    }
    (output / "multiworld_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
