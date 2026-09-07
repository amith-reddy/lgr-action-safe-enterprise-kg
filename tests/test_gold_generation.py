from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_evomem_enterprise import resolve_declared_conflict


def row(assertion_id: str, value: str, source: str, record_time: str) -> dict:
    return {
        "assertion_id": assertion_id,
        "predicate": "account_owner",
        "object": value,
        "source": source,
        "record_time": record_time,
        "lifecycle_state": "active",
    }


class GoldConflictResolutionTests(unittest.TestCase):
    def resolve(self, rows: list[dict]) -> list[str]:
        return resolve_declared_conflict(
            [item["assertion_id"] for item in rows],
            {item["assertion_id"]: item for item in rows},
            "account_owner",
            "2026-06-01T00:00:00Z",
            {"account_owner": ["crm", "support_note"]},
        )

    def test_authority_precedes_recency(self):
        rows = [
            row("high", "owner_a", "crm", "2026-05-01T00:00:00Z"),
            row("low", "owner_b", "support_note", "2026-05-20T00:00:00Z"),
        ]
        self.assertEqual(self.resolve(rows), ["high"])

    def test_recency_breaks_equal_authority(self):
        rows = [
            row("old", "owner_a", "crm", "2026-05-01T00:00:00Z"),
            row("new", "owner_b", "crm", "2026-05-20T00:00:00Z"),
        ]
        self.assertEqual(self.resolve(rows), ["new"])

    def test_incompatible_top_tie_is_unresolved(self):
        rows = [
            row("a", "owner_a", "crm", "2026-05-20T00:00:00Z"),
            row("b", "owner_b", "crm", "2026-05-20T00:00:00Z"),
        ]
        self.assertEqual(self.resolve(rows), [])

    def test_equivalent_top_tie_retains_both(self):
        rows = [
            row("a", "owner_a", "crm", "2026-05-20T00:00:00Z"),
            row("b", "owner_a", "crm", "2026-05-20T00:00:00Z"),
        ]
        self.assertEqual(self.resolve(rows), ["a", "b"])

    def test_corrected_frozen_owner_labels_remain_winners(self):
        generated = ROOT / "data" / "evomem_enterprise" / "generated"
        gold = {
            item["task_id"]: item
            for item in map(json.loads, (generated / "gold_test.jsonl").read_text().splitlines())
        }
        self.assertEqual(gold["t_00022"]["eligible_assertion_ids"], ["a_00527"])
        self.assertEqual(gold["t_00029"]["eligible_assertion_ids"], ["a_00485"])


if __name__ == "__main__":
    unittest.main()
