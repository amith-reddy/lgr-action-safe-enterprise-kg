#!/usr/bin/env python3
"""Emit the declared provenance-activity registry for the frozen corpus.

The manuscript's ProvOK predicate requires gamma != bot and fromSource(gamma)
= mu: an assertion must cite a provenance record that exists and that is
attributed to the assertion's own originating source.  That check is only
meaningful against a registry held independently of the assertion stream --
if the operator derived the registry from whatever assertions it was handed,
every assertion would vouch for itself and a dangling citation would pass.

This script derives the registry once from the frozen assertion ledger and
writes it as a first-class artifact (PROV-O style: activities are nodes, not
string attributes).  It is read-only with respect to the ledger and rejects a
corpus in which one activity is attributed to two different sources.
"""

from __future__ import annotations

import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evomem_enterprise"
LEDGER = DATA / "generated" / "assertion_events.jsonl"
OUT = DATA / "generated" / "provenance_activities.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main(data_root: Path | None = None) -> int:
    global DATA, LEDGER, OUT
    if data_root is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--data-root", type=Path, default=DATA)
        data_root = parser.parse_args().data_root
    DATA = data_root.resolve()
    LEDGER = DATA / "generated" / "assertion_events.jsonl"
    OUT = DATA / "generated" / "provenance_activities.jsonl"
    assertions = load_jsonl(LEDGER)
    by_activity: dict[str, set[str]] = defaultdict(set)
    cited_by: dict[str, list[str]] = defaultdict(list)
    for row in assertions:
        activity = row.get("provenance_activity")
        source = row.get("source")
        if not activity or not source:
            continue
        by_activity[activity].add(source)
        cited_by[activity].append(row["assertion_id"])

    conflicts = {a: sorted(s) for a, s in by_activity.items() if len(s) > 1}
    if conflicts:
        print(json.dumps({"status": "fail", "activities_with_multiple_sources": conflicts}, indent=2))
        return 1

    rows = [
        {
            "activity_id": activity,
            "source": sorted(sources)[0],
            "cited_by_assertion_ids": sorted(cited_by[activity]),
        }
        for activity, sources in sorted(by_activity.items())
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": "pass",
                "activities": len(rows),
                "assertions_scanned": len(assertions),
                "assertions_without_provenance": sum(
                    1 for r in assertions if not r.get("provenance_activity") or not r.get("source")
                ),
                "output": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
