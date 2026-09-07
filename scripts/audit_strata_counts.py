"""Independent audit of EvoMem-Enterprise test-split strata counts.

Read-only. Recomputes the counts and denominators the manuscript cites so that
every number in the paper traces to a local artifact rather than to a prose
summary in the Phase 2/3 planning documents.
"""

import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "data/evomem_enterprise/generated"
P3 = ROOT / "data/evomem_enterprise/phase3"


def load(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    gold = load(GEN / "gold_test.jsonl")
    tasks = load(GEN / "tasks_test.jsonl")
    assertions = load(GEN / "assertion_events.jsonl")
    entities = load(GEN / "entities.jsonl")
    groups = load(GEN / "contradiction_groups.jsonl")

    print("== corpus ==")
    print("assertion_events:", len(assertions))
    print("entities:", len(entities))
    print("contradiction_groups:", len(groups))
    print("test tasks:", len(tasks), "gold:", len(gold))

    print("\n== gold schema ==")
    print("gold keys:", sorted(gold[0].keys()))
    print("task keys:", sorted(tasks[0].keys()))

    print("\n== task strata ==")
    print("task_type:", dict(collections.Counter(t["task_type"] for t in tasks)))
    print("retrieval_mode:", dict(collections.Counter(t.get("retrieval_mode") for t in tasks)))
    print("with candidate_actions:", sum(1 for t in tasks if t.get("candidate_actions")))
    print("with workflow_instance_id:", sum(1 for t in tasks if t.get("workflow_instance_id")))
    print("with disallowed_sources:", sum(1 for t in tasks if t.get("disallowed_sources")))

    print("\n== gold strata ==")
    print("has contradiction_winner_ids:", sum(1 for g in gold if g.get("contradiction_winner_ids")))
    print("has stale_or_superseded:", sum(1 for g in gold if g.get("stale_or_superseded_assertion_ids")))
    print("empty valid_actions:", sum(1 for g in gold if not g.get("valid_actions")))
    print("nonempty valid_actions:", sum(1 for g in gold if g.get("valid_actions")))

    reasons = collections.Counter()
    tasks_with_reason = collections.Counter()
    for g in gold:
        seen = set()
        for rs in (g.get("expected_suppression") or {}).values():
            for r in (rs if isinstance(rs, list) else [rs]):
                reasons[r] += 1
                seen.add(r)
        for r in seen:
            tasks_with_reason[r] += 1
    print("\nsuppression reason -> assertion count:", dict(reasons))
    print("suppression reason -> task count:", dict(tasks_with_reason))

    # assertion-level corpus properties
    print("\n== assertion corpus ==")
    print("lifecycle_state:", dict(collections.Counter(a.get("lifecycle_state") for a in assertions)))
    print("assertion_type:", dict(collections.Counter(a.get("assertion_type") for a in assertions)))
    print("source:", dict(collections.Counter(a.get("source") for a in assertions)))
    print("with superseded_by:", sum(1 for a in assertions if a.get("superseded_by")))
    print("with contradiction_group:", sum(1 for a in assertions if a.get("contradiction_group")))
    print("missing source:", sum(1 for a in assertions if not a.get("source")))
    print("ontology_version:", dict(collections.Counter(a.get("ontology_version") for a in assertions)))
    print("policy_version:", dict(collections.Counter(a.get("policy_version") for a in assertions)))

    # contradiction group sizes / tie potential
    sizes = collections.Counter()
    for grp in groups:
        members = grp.get("member_assertion_ids") or grp.get("members") or []
        sizes[len(members)] += 1
    print("\ncontradiction group size histogram:", dict(sizes))
    print("group keys:", sorted(groups[0].keys()))

    # LGR contradiction winner behaviour, recomputed from packets
    packets = [json.loads(l) for l in (P3 / "context_packets_test.jsonl").open(encoding="utf-8")]
    lgr = {p["task_id"]: p for p in packets if p["method"] == "lifecycle_governed_kg_retrieval"}
    goldby = {g["task_id"]: g for g in gold}
    num, den, tasks_scored = 0, 0, 0
    for tid, p in lgr.items():
        wins = set(goldby[tid].get("contradiction_winner_ids") or [])
        if not wins:
            continue
        tasks_scored += 1
        num += len(set(p["retrieved_assertion_ids"]) & wins)
        den += len(wins)
    print("\n== contradiction winner recall (LGR, recomputed) ==")
    print("tasks with winner ids:", tasks_scored, "micro winners hit:", num, "/", den)

    print("\npacket keys:", sorted(packets[0].keys()))
    ex = lgr[next(iter(lgr))]
    print("suppressed_assertion_ids present:", "suppressed_assertion_ids" in ex)
    print("suppression reason field present:",
          [k for k in ex.keys() if "reason" in k.lower() or "suppress" in k.lower()])


if __name__ == "__main__":
    main()
