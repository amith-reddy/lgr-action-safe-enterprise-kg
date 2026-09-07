#!/usr/bin/env python3
"""Executable reference implementation of lifecycle-governed retrieval.

This module is deliberately independent of benchmark-label generation.  It
implements the staged operator described in the manuscript: assertion
eligibility, query-normalized conflict resolution, table-driven action
admission, witness traces, and content-addressed snapshots.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


POLICY_ASSERTION_TYPES = {
    "policy_fact",
    "action_permission",
    "workflow_policy_binding",
}

# Assertion types entitled to declare which entities take part in a workflow
# case.  Membership is a governance statement, so only the workflow record
# itself may make it.
WORKFLOW_ASSERTION_TYPES = {
    "workflow_fact",
}

RELATION_EQUIVALENTS = {
    "support_plan": {"support_plan", "entitlement_profile", "support_entitlement"},
    "entitlement_profile": {
        "support_plan",
        "entitlement_profile",
        "support_entitlement",
        "product_entitlement",
        "contractual_entitlement",
    },
    "support_entitlement": {"support_plan", "entitlement_profile", "support_entitlement"},
    "owner": {"owner", "account_owner"},
    "account_owner": {"owner", "account_owner"},
    "refund_status": {"refund_status", "workflow_state"},
    "workflow_state": {"refund_status", "workflow_state"},
}

# Canonical name of each renaming class.  Two names in one class denote the same
# decision variable across ontology versions and must normalize to a single key,
# or a conflict could hide behind a renamed relation.  Names in different classes
# denote different variables, so a mapping reaching more than one class is
# genuinely ambiguous.  Each canonical name below is the name the trust and
# conflict-semantics tables declare.
RELATION_CANONICAL = {
    "support_plan": "support_entitlement",
    "entitlement_profile": "support_entitlement",
    "support_entitlement": "support_entitlement",
    "owner": "account_owner",
    "account_owner": "account_owner",
    "refund_status": "workflow_state",
    "workflow_state": "workflow_state",
}


def canonical_relation(relation: str | None) -> str | None:
    if relation is None:
        return None
    return RELATION_CANONICAL.get(relation, relation)


class MalformedTimestamp(ValueError):
    """A timestamp field was present but could not be parsed as an instant."""


def parse_time(value: str | None) -> datetime | None:
    """Parse an absent-or-valid instant.

    An absent field returns None (an open interval boundary).  A field that is
    present but unparseable, or that carries no timezone, raises rather than
    silently degrading to "unbounded": treating a malformed boundary as an
    absent one would admit an assertion whose validity cannot be established.
    """
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MalformedTimestamp(f"unparseable timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise MalformedTimestamp(f"timestamp {value!r} has no timezone offset")
    return parsed


def parse_time_lenient(value: str | None) -> datetime | None:
    """parse_time for contexts that rank rather than authorize."""
    try:
        return parse_time(value)
    except MalformedTimestamp:
        return None


def temporal_field_errors(assertion: dict) -> list[str]:
    """Return a reason code when any decision-relevant instant is malformed."""
    for field in ("record_time", "valid_from", "valid_until"):
        try:
            parse_time(assertion.get(field))
        except MalformedTimestamp:
            return ["temporal_field_malformed"]
    return []


def provenance_index(assertions: Iterable[dict]) -> dict[str, set[str]]:
    """Map each provenance activity in the snapshot to the sources citing it.

    This is the `fromSource` relation of the manuscript's ProvOK predicate.  It
    is built from the supplied snapshot, so an assertion naming an activity
    that no record in the snapshot defines is a dangling reference.
    """
    index: dict[str, set[str]] = {}
    for row in assertions:
        activity = row.get("provenance_activity")
        source = row.get("source")
        if isinstance(activity, str) and activity and isinstance(source, str) and source:
            index.setdefault(activity, set()).add(source)
    return index


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def validate_trust_table(
    document: dict,
    *,
    expected_version: str | None = None,
    required_relations: Iterable[str] = (),
    required_pairs: Iterable[tuple[str, str]] = (),
) -> None:
    version = document.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("trust table has no version")
    if expected_version is not None and version != expected_version:
        raise ValueError(f"trust-table version mismatch: expected {expected_version}, found {version}")
    relations = document.get("relations")
    if not isinstance(relations, dict):
        raise ValueError("trust table has no relation map")
    missing = sorted(set(required_relations) - set(relations))
    if missing:
        raise ValueError(f"trust table is missing relations: {', '.join(missing)}")
    for relation, tiers in relations.items():
        if not isinstance(tiers, list) or not tiers:
            raise ValueError(f"trust relation {relation!r} has no tiers")
        if any(not isinstance(tier, str) or not tier for tier in tiers):
            raise ValueError(f"trust relation {relation!r} has an invalid tier")
        duplicates = sorted({tier for tier in tiers if tiers.count(tier) > 1})
        if duplicates:
            raise ValueError(f"trust relation {relation!r} has duplicate tiers: {', '.join(duplicates)}")
    missing_pairs = sorted(
        (relation, source)
        for relation, source in set(required_pairs)
        if source not in relations.get(relation, [])
    )
    if missing_pairs:
        rendered = ", ".join(f"{relation}/{source}" for relation, source in missing_pairs)
        raise ValueError(f"trust table is missing relation/source pairs: {rendered}")


def validate_conflict_semantics(document: dict, *, required_relations: Iterable[str] = ()) -> None:
    """Validate relation-specific conflict semantics.

    A conflict key identifies assertions about the same decision variable; it
    does not contain the asserted value.  Whether two distinct values are
    incompatible is a relation-level governance choice.
    """
    version = document.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("conflict semantics has no version")
    relations = document.get("relations")
    if not isinstance(relations, dict):
        raise ValueError("conflict semantics has no relation map")
    missing = sorted(set(required_relations) - set(relations))
    if missing:
        raise ValueError(f"conflict semantics is missing relations: {', '.join(missing)}")
    for relation, spec in relations.items():
        if not isinstance(spec, dict):
            raise ValueError(f"conflict semantics for {relation!r} is not an object")
        if spec.get("cardinality") not in {"single_value", "multi_value"}:
            raise ValueError(f"conflict semantics for {relation!r} has invalid cardinality")
        if spec.get("key") not in {"subject", "workflow_or_subject"}:
            raise ValueError(f"conflict semantics for {relation!r} has invalid key")
        if spec.get("incompatibility") not in {"distinct_values", "none"}:
            raise ValueError(f"conflict semantics for {relation!r} has invalid incompatibility rule")
        if spec["cardinality"] == "multi_value" and spec["incompatibility"] != "none":
            raise ValueError(f"multi-value relation {relation!r} cannot use distinct-values conflict resolution")


@dataclass(frozen=True)
class GovernanceBundle:
    data_root: Path
    trust_version: str
    trust_relations: dict[str, list[str]]
    source_catalog_version: str
    required_source_pairs: tuple[tuple[str, str], ...]
    action_registry_version: str
    actions: dict[str, dict]
    policies: dict[str, list[dict]]
    workflows: dict[str, dict]
    ontology_mappings: list[dict]
    conflict_semantics_version: str
    conflict_semantics: dict[str, dict]
    provenance_activities: dict[str, str]

    @classmethod
    def load(cls, data_root: Path) -> "GovernanceBundle":
        trust_doc = load_json(data_root / "config" / "trust_precedence.json")
        source_doc = load_json(data_root / "config" / "source_catalog.json")
        source_relations = source_doc.get("action_relevant_relations")
        if not isinstance(source_relations, dict):
            raise ValueError("source catalog has no action-relevant relation map")
        required_source_pairs: list[tuple[str, str]] = []
        for relation, sources in source_relations.items():
            if not isinstance(sources, list) or not sources:
                raise ValueError(f"source catalog relation {relation!r} has no declared sources")
            required_source_pairs.extend((relation, source) for source in sources)
        validate_trust_table(trust_doc, required_pairs=required_source_pairs)
        provenance_path = data_root / "generated" / "provenance_activities.jsonl"
        provenance_activities: dict[str, str] = {}
        if not provenance_path.exists():
            # ProvOK is a required admission predicate, so a missing registry is
            # a governance misconfiguration, not an empty one.  Loading it as
            # empty would silently disable the check for every assertion.
            raise ValueError(
                f"provenance activity registry is missing at {provenance_path}; "
                "run scripts/build_provenance_registry.py"
            )
        for row in load_jsonl(provenance_path):
            activity = row.get("activity_id")
            source = row.get("source")
            if not isinstance(activity, str) or not activity:
                raise ValueError("provenance registry contains an unnamed activity")
            if not isinstance(source, str) or not source:
                raise ValueError(f"provenance activity {activity!r} has no source")
            if activity in provenance_activities and provenance_activities[activity] != source:
                raise ValueError(f"provenance activity {activity!r} is attributed to two sources")
            provenance_activities[activity] = source
        if not provenance_activities:
            raise ValueError(f"provenance activity registry at {provenance_path} is empty")
        conflict_doc = load_json(data_root / "config" / "conflict_semantics.json")
        validate_conflict_semantics(conflict_doc, required_relations=trust_doc["relations"])
        registry_doc = load_json(data_root / "config" / "action_registry.json")
        registry_rows = registry_doc.get("actions")
        if not isinstance(registry_rows, list):
            raise ValueError("action registry has no actions")
        actions: dict[str, dict] = {}
        for row in registry_rows:
            action = row.get("action")
            if not isinstance(action, str) or not action:
                raise ValueError("action registry contains an unnamed action")
            if action in actions:
                raise ValueError(f"action registry contains duplicate action {action}")
            if row.get("kind") not in {"advisory", "effectful"}:
                raise ValueError(f"action registry contains invalid kind for {action}")
            if row.get("kind") == "effectful":
                if not row.get("policy_family"):
                    raise ValueError(f"effectful action {action} has no policy family")
                if not row.get("workflow_type"):
                    raise ValueError(f"effectful action {action} has no workflow type")
            actions[action] = row

        policies: dict[str, list[dict]] = {}
        for path in sorted((data_root / "policy").glob("*.json")):
            doc = load_json(path)
            for rule in doc.get("rules", []):
                version = rule.get("policy_version")
                if not version:
                    raise ValueError(f"policy rule in {path.name} has no version")
                if not rule.get("policy_family"):
                    raise ValueError(f"policy rule in {path.name} has no policy family")
                policies.setdefault(version, []).append(rule)

        workflows: dict[str, dict] = {}
        for path in sorted((data_root / "workflows").glob("*.json")):
            doc = load_json(path)
            workflow_type = doc.get("workflow_type")
            if not workflow_type:
                raise ValueError(f"workflow {path.name} has no workflow_type")
            workflows[workflow_type] = doc

        mappings = load_json(data_root / "ontology" / "ontology_mappings.json").get("mappings", [])
        return cls(
            data_root=data_root,
            trust_version=trust_doc["version"],
            trust_relations=trust_doc["relations"],
            source_catalog_version=source_doc.get("version", ""),
            required_source_pairs=tuple(sorted(required_source_pairs)),
            action_registry_version=registry_doc.get("version", ""),
            actions=actions,
            policies=policies,
            workflows=workflows,
            ontology_mappings=mappings,
            conflict_semantics_version=conflict_doc["version"],
            conflict_semantics=conflict_doc["relations"],
            provenance_activities=provenance_activities,
        )

    def validate_for_task(self, task: dict) -> None:
        required_relations = set(task.get("relation_scope") or [])
        validate_trust_table(
            {"version": self.trust_version, "relations": self.trust_relations},
            expected_version=task.get("trust_table_version", self.trust_version),
            required_relations=required_relations,
            required_pairs=self.required_source_pairs,
        )
        validate_conflict_semantics(
            {"version": self.conflict_semantics_version, "relations": self.conflict_semantics},
            required_relations=required_relations,
        )
        for action in task.get("candidate_actions") or []:
            if action not in self.actions:
                # Missing registration is a normal default-deny outcome.  The
                # registry itself is still structurally valid.
                continue


def _mapping_targets(predicate: str, source_version: str, target_version: str, mappings: list[dict]) -> set[str]:
    frontier = {(source_version, predicate)}
    visited: set[tuple[str, str]] = set()
    targets: set[str] = set()
    while frontier:
        version, relation = frontier.pop()
        if (version, relation) in visited:
            continue
        visited.add((version, relation))
        if version == target_version:
            targets.add(relation)
            continue
        for mapping in mappings:
            if mapping.get("from_ov") == version and mapping.get("from_relation") == relation:
                frontier.add((mapping.get("to_ov"), mapping.get("to_relation")))
    return targets


def normalization_candidates(
    assertion: dict, task: dict, governance: GovernanceBundle, *, scope: Iterable[str] | None = None
) -> list[str]:
    """Return every canonical relation this assertion could normalize to.

    Normalization is a property of the assertion and the target ontology
    version alone: it does not consult the query.  Names that denote the same
    decision variable collapse to one canonical form; if the mapping still
    reaches more than one distinct variable the mapping is genuinely split, and
    callers refuse rather than pick a branch.  Letting the query's relation
    scope break the tie would make the same assertion mean different things to
    different queries, and letting sort order break it would make the meaning an
    artifact of spelling.

    The query's scope still decides *coverage* (see `covers_relation`); it never
    decides identity.
    """
    predicate = assertion.get("predicate")
    source_version = assertion.get("ontology_version")
    target_version = task.get("target_ontology_version")
    if not predicate or not source_version or not target_version:
        return []
    targets = _mapping_targets(predicate, source_version, target_version, governance.ontology_mappings)
    if source_version == target_version:
        targets.add(predicate)
    canonical = {canonical_relation(target) for target in targets if target}
    return sorted(name for name in canonical if name)


def normalized_relation(
    assertion: dict, task: dict, governance: GovernanceBundle, *, scope: Iterable[str] | None = None
) -> str | None:
    """Deterministically normalize a predicate, or None if it cannot be."""
    candidates = normalization_candidates(assertion, task, governance, scope=scope)
    if len(candidates) != 1:
        return None
    return candidates[0]


def covers_entity(assertion: dict, task: dict) -> bool:
    query_scope = set(task.get("entity_scope") or [])
    assertion_scope = set(assertion.get("entity_scope") or [])
    if assertion.get("subject") in query_scope or query_scope & assertion_scope:
        return True
    workflow_id = task.get("workflow_instance_id")
    return bool(workflow_id and assertion.get("workflow_instance_id") == workflow_id)


def decision_scope_relations(task: dict, governance: GovernanceBundle) -> list[str]:
    """Relations admissible as decision evidence for this query.

    This is the query's own relation scope together with every relation the
    registered candidate actions' policy and workflow guards declare.  Keeping
    it distinct from the retrieval scope is what makes dependency completion
    meaningful: a guard witness gathered by the closure must also survive
    eligibility, which it cannot do if eligibility only admits the relations
    the query happened to name.
    """
    requested = list(task.get("relation_scope") or [])
    seen = set(requested)
    for relation in sorted(action_dependency_relations(task, governance)):
        if relation not in seen:
            requested.append(relation)
            seen.add(relation)
    return requested


def covers_relation(
    assertion: dict, task: dict, governance: GovernanceBundle, *, scope: Iterable[str] | None = None
) -> bool:
    relations = list(scope) if scope is not None else decision_scope_relations(task, governance)
    relation = normalized_relation(assertion, task, governance, scope=relations)
    # Compare canonical forms: a query naming an older relation name still
    # covers evidence recorded under the current name for the same variable.
    return bool(relation and relation in {canonical_relation(r) for r in relations})


def _time_valid(assertion: dict, when: datetime) -> bool:
    start = parse_time(assertion.get("valid_from"))
    end = parse_time(assertion.get("valid_until"))
    return (start is None or start <= when) and (end is None or when < end)


def query_time(task: dict) -> datetime | None:
    """Return the time at which the selected graph snapshot is observed."""
    if task.get("retrieval_mode") == "audit_historical":
        return parse_time(task.get("audit_time"))
    return parse_time(task.get("decision_time"))


def _record_is_visible(assertion: dict, when: datetime | None) -> bool:
    recorded = parse_time(assertion.get("record_time"))
    return bool(when is not None and recorded is not None and recorded <= when)


def _visible_successors(assertion: dict, assertion_index: dict[str, dict], when: datetime | None) -> list[dict]:
    return [
        assertion_index[successor_id]
        for successor_id in assertion.get("superseded_by") or []
        if successor_id in assertion_index and _record_is_visible(assertion_index[successor_id], when)
    ]


def validate_supersession_graph(assertion_index: dict[str, dict]) -> None:
    """Reject dangling, cross-subject, and cyclic replacement relationships."""
    edges: dict[str, set[str]] = {assertion_id: set() for assertion_id in assertion_index}
    for assertion_id, assertion in assertion_index.items():
        for successor_id in assertion.get("superseded_by") or []:
            successor = assertion_index.get(successor_id)
            if successor is None:
                raise ValueError(f"supersession successor {successor_id!r} is missing")
            if successor.get("subject") != assertion.get("subject"):
                raise ValueError("supersession crosses subjects")
            edges[assertion_id].add(successor_id)
        for predecessor_id in assertion.get("supersedes") or []:
            predecessor = assertion_index.get(predecessor_id)
            if predecessor is None:
                raise ValueError(f"supersession predecessor {predecessor_id!r} is missing")
            if predecessor.get("subject") != assertion.get("subject"):
                raise ValueError("supersession crosses subjects")
            edges[predecessor_id].add(assertion_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(assertion_id: str) -> None:
        if assertion_id in visiting:
            raise ValueError("supersession cycle detected")
        if assertion_id in visited:
            return
        visiting.add(assertion_id)
        for successor_id in edges[assertion_id]:
            visit(successor_id)
        visiting.remove(assertion_id)
        visited.add(assertion_id)

    for assertion_id in sorted(edges):
        visit(assertion_id)


def eligibility_reasons(
    assertion: dict,
    task: dict,
    cfg: dict,
    governance: GovernanceBundle,
    assertion_index: dict[str, dict] | None = None,
    *,
    scope: Iterable[str] | None = None,
    provenance: dict[str, set[str]] | None = None,
) -> list[str]:
    """Return every failed Stage-1 predicate as a stable reason code."""
    reasons: list[str] = []
    relations = list(scope) if scope is not None else decision_scope_relations(task, governance)

    # A malformed decision-relevant instant is checked first: every later
    # temporal predicate would otherwise read it as an open boundary.
    malformed = temporal_field_errors(assertion)
    if malformed:
        reasons.extend(malformed)

    if cfg.get("use_entity_scope", True) and not covers_entity(assertion, task):
        reasons.append("scope_entity_mismatch")
    if cfg.get("use_relation_scope", True) and not covers_relation(
        assertion, task, governance, scope=relations
    ):
        reasons.append("scope_relation_mismatch")

    mode = task.get("retrieval_mode", "current_action")
    when = query_time(task)
    if cfg.get("use_record_visibility", cfg.get("use_validity_interval", True)) and not malformed:
        if not _record_is_visible(assertion, when):
            reasons.append("record_not_visible")
    if cfg.get("use_validity_interval", True) and not malformed:
        if when is None or not _time_valid(assertion, when):
            reasons.append("time_invalid")

    if cfg.get("use_lifecycle_state", True):
        state = assertion.get("lifecycle_state")
        if mode == "current_action" and state != "active":
            reasons.append("lifecycle_ineligible")
        elif mode == "audit_historical" and state in {"deleted", "retracted"}:
            reasons.append("lifecycle_ineligible")

    if cfg.get("use_ontology_versioning", True):
        candidates = normalization_candidates(assertion, task, governance, scope=relations)
        if len(candidates) > 1:
            # A split mapping the scope does not disambiguate. Choosing a branch
            # by scope order would let the query's relation ordering decide the
            # value's meaning, so the assertion is not eligible evidence.
            reasons.append("ontology_ambiguous")
        elif not candidates:
            reasons.append("ontology_incompatible")

    if (
        cfg.get("use_policy_versioning", True)
        and assertion.get("assertion_type") in POLICY_ASSERTION_TYPES
        and assertion.get("policy_version") != task.get("target_policy_version")
    ):
        reasons.append("policy_version_incompatible")

    if cfg.get("use_provenance_activity", cfg.get("use_provenance_trust", True)):
        activity = assertion.get("provenance_activity")
        source = assertion.get("source")
        if not activity or not source:
            reasons.append("provenance_missing")
        else:
            # ProvOK requires fromSource(gamma) == mu: the cited activity must
            # resolve in the declared provenance registry and be attributed to
            # this assertion's source.  The registry is a governance artifact
            # held apart from the assertion stream, so an assertion cannot
            # vouch for its own citation.
            # An absent or empty registry resolves nothing, so every citation is
            # unresolved.  Skipping the check in that case would let a missing
            # governance artifact silently admit evidence it cannot vouch for.
            registry = provenance if provenance is not None else governance.provenance_activities
            declared = (registry or {}).get(activity)
            if declared is None:
                reasons.append("provenance_unresolved")
            elif declared != source:
                reasons.append("provenance_source_mismatch")
    if cfg.get("use_source_eligibility", cfg.get("use_provenance_trust", True)):
        source = assertion.get("source")
        if source in set(task.get("disallowed_sources") or []):
            reasons.append("source_disallowed")
        relation = normalized_relation(assertion, task, governance, scope=relations)
        tiers = governance.trust_relations.get(relation or "", [])
        if not source or source not in tiers:
            reasons.append("source_untrusted")

    if cfg.get("use_supersession_links", True) and mode == "current_action" and assertion.get("superseded_by"):
        if assertion_index is None:
            reasons.append("superseded")
        else:
            # Replacement is permanent once the replacement record is visible.
            # A later active assertion can re-establish a value only by being a
            # new assertion event, never by silently reviving this predecessor.
            if _visible_successors(assertion, assertion_index, when):
                reasons.append("superseded")

    if cfg.get("use_workflow_instance_scope", cfg.get("use_workflow_state_binding", True)):
        query_workflow = task.get("workflow_instance_id")
        assertion_workflow = assertion.get("workflow_instance_id")
        if assertion_workflow and query_workflow and assertion_workflow != query_workflow:
            reasons.append("workflow_instance_mismatch")
    return reasons


def _trust_rank(assertion: dict, relation: str, governance: GovernanceBundle) -> int:
    tiers = governance.trust_relations.get(relation, [])
    source = assertion.get("source")
    return tiers.index(source) if source in tiers else len(tiers) + 1


def conflict_key(assertion: dict, task: dict, governance: GovernanceBundle) -> tuple[str, str] | None:
    """Return a decision-variable key, never a value-bearing triple key."""
    relation = normalized_relation(assertion, task, governance)
    if relation is None:
        return None
    semantics = governance.conflict_semantics.get(relation)
    if semantics is None:
        raise ValueError(f"no conflict semantics declared for {relation!r}")
    if semantics["cardinality"] == "multi_value":
        return None
    if semantics["key"] == "workflow_or_subject":
        owner = assertion.get("workflow_instance_id") or assertion.get("subject")
    else:
        owner = assertion.get("subject")
    return (str(owner), relation)


def value_signature(assertion: dict) -> str:
    return canonical_json(assertion.get("object")).decode("utf-8")


def resolve_conflicts(
    eligible: list[dict],
    task: dict,
    governance: GovernanceBundle,
    *,
    enabled: bool = True,
    use_trust: bool = True,
) -> tuple[list[dict], dict[str, list[str]], list[dict], list[dict]]:
    """Resolve incompatible values by trust and descending record time.

    No assertion identifier is used as a semantic tie-break.  A top-tier,
    same-time tie between different values is emitted as unresolved.
    """
    if not enabled or task.get("retrieval_mode") == "audit_historical":
        return list(eligible), {}, [], []
    grouped: dict[tuple[str, str], list[dict]] = {}
    for assertion in eligible:
        key = conflict_key(assertion, task, governance)
        if key is not None:
            grouped.setdefault(key, []).append(assertion)

    suppressed: dict[str, list[str]] = {}
    unresolved: list[dict] = []
    traces: list[dict] = []
    removed: set[str] = set()
    for (subject, relation), rows in sorted(grouped.items()):
        values = {value_signature(row) for row in rows}
        if len(values) < 2:
            continue
        best_rank = min(_trust_rank(row, relation, governance) for row in rows) if use_trust else None
        trusted = [row for row in rows if not use_trust or _trust_rank(row, relation, governance) == best_rank]
        newest_time = max(
            parse_time_lenient(row.get("record_time")) or datetime.min.replace(tzinfo=timezone.utc)
            for row in trusted
        )
        finalists = [
            row
            for row in trusted
            if (parse_time_lenient(row.get("record_time")) or datetime.min.replace(tzinfo=timezone.utc)) == newest_time
        ]
        finalist_values = {value_signature(row) for row in finalists}
        if len(finalist_values) > 1:
            ids = sorted(row["assertion_id"] for row in finalists)
            for row in rows:
                removed.add(row["assertion_id"])
                suppressed[row["assertion_id"]] = ["unresolved_conflict"]
            record = {
                "conflict_key": [subject, relation],
                "subject": subject,
                "predicate": relation,
                "assertion_ids": ids,
                "status": "unresolved",
            }
            unresolved.append(record)
            traces.append(record)
            continue

        # Equivalent finalists are not incompatible; retain all equivalent
        # top assertions and suppress only different or lower-ranked values.
        winning_value = next(iter(finalist_values))
        winner_ids = sorted(
            row["assertion_id"]
            for row in finalists
            if value_signature(row) == winning_value
        )
        for row in rows:
            row_value = value_signature(row)
            if row["assertion_id"] not in winner_ids and row_value != winning_value:
                removed.add(row["assertion_id"])
                suppressed[row["assertion_id"]] = ["contradiction_loser"]
        traces.append(
            {
                "conflict_key": [subject, relation],
                "subject": subject,
                "predicate": relation,
                "assertion_ids": sorted(row["assertion_id"] for row in rows),
                "winner_assertion_ids": winner_ids,
                "winning_value": json.loads(winning_value),
                "status": "resolved",
            }
        )
    return [row for row in eligible if row["assertion_id"] not in removed], suppressed, unresolved, traces


def workflow_members(
    workflow_id: str,
    assertions: Iterable[dict],
    governance: GovernanceBundle | None = None,
) -> set[str]:
    """Entities a workflow instance explicitly declares as belonging to its case.

    Membership is read from the case's own workflow assertions, which name their
    participants in `entity_scope`.  Only assertions carrying this workflow's
    identifier and originating from a source trusted for `workflow_state`
    contribute, so an unrelated record cannot enrol itself into a case.
    """
    trusted = set(governance.trust_relations.get("workflow_state", [])) if governance else None
    members: set[str] = set()
    for assertion in assertions:
        if assertion.get("workflow_instance_id") != workflow_id:
            continue
        if assertion.get("assertion_type") not in WORKFLOW_ASSERTION_TYPES:
            continue
        if trusted is not None and assertion.get("source") not in trusted:
            continue
        subject = assertion.get("subject")
        if subject:
            members.add(subject)
        members.update(assertion.get("entity_scope") or [])
    return members


def action_binding(
    task: dict,
    assertions: Iterable[dict] | None = None,
    governance: GovernanceBundle | None = None,
) -> dict:
    """Resolve the single principal an effectful action is evaluated against.

    Guard witnesses must all concern one action target.  Individually eligible
    facts about different principals do not compose into a justification: a
    refund for one account may not be authorized by another account's
    subscription status.  When the query scope cannot be resolved to one
    target, the action is refused rather than evaluated against a mixture.

    The target comes from an explicitly declared `action_target`, or from the
    membership a workflow instance itself asserts.  It is never inferred from
    how identifiers are spelled: identifier shape is a naming convention, not an
    authorization relation, and two unrelated entities may share any affix.
    """
    declared = task.get("action_target")
    workflow_id = task.get("workflow_instance_id")
    scope = [e for e in (task.get("entity_scope") or [])]
    if declared:
        return {"subject": declared, "workflow_instance_id": workflow_id, "ambiguous": False}
    if workflow_id and assertions is not None:
        declared_members = workflow_members(workflow_id, assertions, governance)
        # Only entities the case declares *and* the query put in scope.
        related = sorted(declared_members & set(scope)) if scope else sorted(declared_members)
        if related:
            return {
                "subject": None,
                "workflow_instance_id": workflow_id,
                "members": sorted(set(related) | {workflow_id}),
                "membership_basis": "declared_workflow_membership",
                "ambiguous": False,
            }
    if len(scope) == 1:
        return {"subject": scope[0], "workflow_instance_id": workflow_id, "ambiguous": False}
    if workflow_id and not scope:
        return {"subject": None, "workflow_instance_id": workflow_id, "members": [workflow_id], "ambiguous": False}
    return {
        "subject": None,
        "workflow_instance_id": workflow_id,
        "members": sorted(scope),
        "ambiguous": len(scope) > 1,
    }


def binds_to_action(assertion: dict, binding: dict) -> bool:
    """True when this assertion concerns the action's bound principal."""
    if assertion.get("assertion_type") in POLICY_ASSERTION_TYPES:
        return True  # governance facts are not entity-scoped
    workflow_id = binding.get("workflow_instance_id")
    assertion_workflow = assertion.get("workflow_instance_id")
    if assertion_workflow and workflow_id and assertion_workflow != workflow_id:
        return False
    members = set(binding.get("members") or [])
    if binding.get("subject"):
        members.add(binding["subject"])
    if not members:
        return True
    if assertion.get("subject") in members:
        return True
    if members & set(assertion.get("entity_scope") or []):
        return True
    return bool(assertion_workflow and workflow_id and assertion_workflow == workflow_id)


def _facts(
    assertions: list[dict],
    task: dict,
    governance: GovernanceBundle,
    *,
    binding: dict | None = None,
) -> dict[str, list[dict]]:
    """Group decision evidence by normalized relation for guard evaluation.

    When a binding is supplied, only assertions concerning that principal are
    grouped, so a guard cannot be satisfied by a fact about another entity.
    """
    scope = decision_scope_relations(task, governance)
    facts: dict[str, list[dict]] = {}
    for assertion in assertions:
        if binding is not None and not binds_to_action(assertion, binding):
            continue
        relation = normalized_relation(assertion, task, governance, scope=scope) or assertion.get("predicate")
        if relation:
            facts.setdefault(relation, []).append(assertion)
    for rows in facts.values():
        rows.sort(key=lambda row: (row.get("record_time") or "", row["assertion_id"]), reverse=True)
    return facts


def guard_predicates(expression: dict | None) -> set[str]:
    if not expression:
        return set()
    if "and" in expression:
        result: set[str] = set()
        for child in expression["and"]:
            result |= guard_predicates(child)
        return result
    for operator in ("equals", "not_equals", "in"):
        if operator in expression:
            return {expression[operator][0]}
    if "exists" in expression:
        return {expression["exists"]}
    return set()


def action_dependency_relations(task: dict, governance: GovernanceBundle) -> set[str]:
    """Return every relation whose evidence can affect an action decision."""
    relations = set(task.get("relation_scope") or [])
    target_policy = task.get("target_policy_version")
    for action in task.get("candidate_actions") or []:
        registration = governance.actions.get(action)
        if registration is None:
            continue
        family = registration.get("policy_family")
        for rule in governance.policies.get(target_policy, []):
            if rule.get("action") == action and rule.get("policy_family") == family:
                relations |= guard_predicates(rule.get("guard"))
        workflow = governance.workflows.get(registration.get("workflow_type"))
        if workflow is not None:
            relations.add("workflow_state")
            for transition in workflow.get("transitions", []):
                if transition.get("action") == action:
                    relations |= guard_predicates(transition.get("guard"))
    return relations


def decision_evidence_completion(
    assertions: list[dict], task: dict, governance: GovernanceBundle
) -> tuple[list[dict], dict]:
    """Close an action decision over its declared evidence dependencies.

    Initial relevance retrieval is intentionally not used here.  The returned
    set is complete only with respect to the supplied, immutable snapshot and
    the relations declared by the query, action guards, and supersession links.
    """
    assertion_index = {row["assertion_id"]: row for row in assertions}
    validate_supersession_graph(assertion_index)
    dependencies = action_dependency_relations(task, governance)
    selected = {
        assertion_id
        for assertion_id, assertion in assertion_index.items()
        if covers_entity(assertion, task)
        and (normalized_relation(assertion, task, governance) or assertion.get("predicate")) in dependencies
    }
    worklist = list(selected)
    while worklist:
        assertion_id = worklist.pop()
        assertion = assertion_index[assertion_id]
        for linked_id in (assertion.get("supersedes") or []) + (assertion.get("superseded_by") or []):
            if linked_id not in selected:
                selected.add(linked_id)
                worklist.append(linked_id)
    rows = [assertion_index[assertion_id] for assertion_id in sorted(selected)]
    return rows, {
        "status": "complete_for_declared_snapshot",
        "dependency_relations": sorted(dependencies),
        "assertion_ids": [row["assertion_id"] for row in rows],
    }


def rule_identifier(rule: dict) -> str:
    """Stable identity of a policy rule, for the replayable decision record."""
    return ":".join(
        str(rule.get(field))
        for field in ("policy_version", "policy_family", "action", "permit_or_deny", "priority")
    )


def transition_identifier(workflow_type: str | None, transition: dict) -> str:
    """Stable identity of a workflow transition, for the decision record."""
    return ":".join(
        str(part)
        for part in (workflow_type, transition.get("action"), transition.get("from"), transition.get("to"))
    )


def evaluate_guard(expression: dict | None, facts: dict[str, list[dict]], task: dict) -> tuple[bool, list[str]]:
    if not expression:
        return True, []
    if "and" in expression:
        witnesses: list[str] = []
        for child in expression["and"]:
            ok, child_witnesses = evaluate_guard(child, facts, task)
            if not ok:
                return False, []
            witnesses.extend(child_witnesses)
        return True, sorted(set(witnesses))
    if "equals" in expression:
        predicate, expected = expression["equals"]
        rows = facts.get(predicate, [])
        return (bool(rows) and rows[0].get("object") == expected, [rows[0]["assertion_id"]] if rows else [])
    if "not_equals" in expression:
        predicate, forbidden = expression["not_equals"]
        rows = facts.get(predicate, [])
        return (bool(rows) and rows[0].get("object") != forbidden, [rows[0]["assertion_id"]] if rows else [])
    if "in" in expression:
        predicate, allowed = expression["in"]
        rows = facts.get(predicate, [])
        return (bool(rows) and rows[0].get("object") in set(allowed), [rows[0]["assertion_id"]] if rows else [])
    if "exists" in expression:
        rows = facts.get(expression["exists"], [])
        return bool(rows), [rows[0]["assertion_id"]] if rows else []
    if "lte_hours_open" in expression:
        value = task.get("hours_open")
        return (value is not None and float(value) <= float(expression["lte_hours_open"]), [])
    return False, []


def admit_actions(
    assertions: list[dict],
    task: dict,
    governance: GovernanceBundle,
    unresolved: list[dict],
    *,
    enforce_binding: bool = True,
) -> dict:
    """Evaluate every candidate action through the default-deny gate.

    `enforce_binding` exists so the workflow/entity-binding control can be
    ablated like any other governance feature.  Disabling it reproduces an
    unbound gate, in which guard witnesses may come from any entity in scope.
    """
    binding = (
        action_binding(task, assertions, governance)
        if enforce_binding
        else {"subject": None, "ambiguous": False}
    )
    facts = _facts(assertions, task, governance, binding=binding if enforce_binding else None)
    mode = task.get("retrieval_mode", "current_action")
    valid: list[str] = []
    blocked: list[str] = []
    blocking_reasons: dict[str, list[str]] = {}
    support: dict[str, list[str]] = {}
    consulted: dict[str, dict] = {}

    for action in task.get("candidate_actions") or []:
        reasons: list[str] = []
        witnesses: set[str] = set()
        registration = governance.actions.get(action)
        if registration is None:
            reasons.append("unregistered_action")
            blocked.append(action)
            blocking_reasons[action] = reasons
            consulted[action] = {"registered": False}
            continue

        action_kind = registration["kind"]
        if action_kind == "effectful":
            # A historical or investigation query explains an earlier decision;
            # it never authorizes a new effectful one.
            if mode != "current_action":
                reasons.append("non_authorizing_query_mode")
            # Every guard witness must concern one action target.
            if binding.get("ambiguous"):
                reasons.append("ambiguous_action_binding")
        if action_kind == "advisory":
            critical = set(registration.get("critical_relations") or [])
            if any(item.get("predicate") in critical for item in unresolved):
                reasons.append("critical_unresolved_conflict")
            if reasons:
                blocked.append(action)
                blocking_reasons[action] = reasons
            else:
                valid.append(action)
                support[action] = []
            consulted[action] = {
                "registered": True,
                "action_kind": action_kind,
                "action_registry_version": governance.action_registry_version,
                "policy_version": None,
                "policy_family": None,
                "workflow_type": None,
                "workflow_state": None,
            }
            continue

        selected_rule: str | None = None
        selected_transition: str | None = None
        target_policy = task.get("target_policy_version")
        expected_policy_family = registration.get("policy_family")
        target_rules = governance.policies.get(target_policy, [])
        target_families = {rule.get("policy_family") for rule in target_rules}
        if target_rules and expected_policy_family not in target_families:
            reasons.append("policy_family_mismatch")
        policy_rules = [
            rule
            for rule in target_rules
            if rule.get("action") == action and rule.get("policy_family") == expected_policy_family
        ]
        satisfied_policy: list[tuple[dict, list[str]]] = []
        for rule in sorted(policy_rules, key=lambda row: row.get("priority", 0), reverse=True):
            ok, ids = evaluate_guard(rule.get("guard"), facts, task)
            if ok:
                satisfied_policy.append((rule, ids))
        if not policy_rules:
            if "policy_family_mismatch" not in reasons:
                reasons.append("missing_policy_binding")
        elif not satisfied_policy:
            reasons.append("policy_guard_failed")
        else:
            highest = max(rule.get("priority", 0) for rule, _ in satisfied_policy)
            highest_rules = [(rule, ids) for rule, ids in satisfied_policy if rule.get("priority", 0) == highest]
            if any(rule.get("permit_or_deny") == "deny" for rule, _ in highest_rules):
                reasons.append("policy_deny")
                selected_rule = rule_identifier(
                    next(rule for rule, _ in highest_rules if rule.get("permit_or_deny") == "deny")
                )
            else:
                permits = [(rule, ids) for rule, ids in highest_rules if rule.get("permit_or_deny") == "permit"]
                if not permits:
                    reasons.append("policy_guard_failed")
                else:
                    witnesses.update(permits[0][1])
                    selected_rule = rule_identifier(permits[0][0])

        workflow_type = registration.get("workflow_type")
        workflow = governance.workflows.get(workflow_type)
        transitions = [] if workflow is None else [row for row in workflow.get("transitions", []) if row.get("action") == action]
        state_rows = facts.get("workflow_state", [])
        current_state = state_rows[0].get("object") if state_rows else None
        applicable = [row for row in transitions if row.get("from") == current_state]
        workflow_passes: list[tuple[dict, list[str]]] = []
        for transition in applicable:
            ok, ids = evaluate_guard(transition.get("guard"), facts, task)
            if ok:
                workflow_passes.append((transition, ids))
        if workflow is None or not transitions:
            reasons.append("missing_workflow_binding")
        elif not state_rows:
            reasons.append("missing_workflow_state_witness")
        elif not workflow_passes:
            reasons.append("workflow_guard_failed")
        else:
            witnesses.update(workflow_passes[0][1])
            selected_transition = transition_identifier(workflow_type, workflow_passes[0][0])

        critical = set()
        for rule in policy_rules:
            critical |= guard_predicates(rule.get("guard"))
        for transition in transitions:
            critical |= guard_predicates(transition.get("guard"))
        if any(item.get("predicate") in critical for item in unresolved):
            reasons.append("critical_unresolved_conflict")

        if not witnesses and not reasons:
            reasons.append("missing_action_witness")
        if reasons:
            blocked.append(action)
            blocking_reasons[action] = sorted(set(reasons))
        else:
            valid.append(action)
            support[action] = sorted(witnesses)
        consulted[action] = {
            "registered": True,
            "action_kind": action_kind,
            "action_registry_version": governance.action_registry_version,
            "policy_version": target_policy,
            "policy_family": expected_policy_family,
            "workflow_type": workflow_type,
            "workflow_state": current_state,
            "selected_policy_rule": selected_rule,
            "selected_workflow_transition": selected_transition,
            "binding_subject": binding.get("subject"),
            "binding_members": binding.get("members"),
            "binding_workflow_instance": binding.get("workflow_instance_id"),
            "query_mode": mode,
        }
    return {
        "valid_actions": valid,
        "blocked_actions": blocked,
        "blocking_reasons": blocking_reasons,
        "support_by_action": support,
        "bindings_consulted": consulted,
    }


def _rank(assertion: dict, task: dict, governance: GovernanceBundle) -> tuple[int, int, str, str]:
    relation = normalized_relation(assertion, task, governance) or assertion.get("predicate") or ""
    exact_relation = 1 if relation in set(task.get("relation_scope") or []) else 0
    trust = -_trust_rank(assertion, relation, governance)
    return (exact_relation, trust, assertion.get("record_time") or "", assertion["assertion_id"])


def evaluate_lgr(
    assertions: list[dict],
    task: dict,
    cfg: dict,
    governance: GovernanceBundle,
    *,
    top_k: int,
) -> dict:
    governance.validate_for_task(task)
    decision_evidence, completion = decision_evidence_completion(assertions, task, governance)
    eligible: list[dict] = []
    suppressed: dict[str, list[str]] = {}
    assertion_index = {row["assertion_id"]: row for row in assertions}
    scope = decision_scope_relations(task, governance)
    for assertion in decision_evidence:
        reasons = eligibility_reasons(
            assertion, task, cfg, governance, assertion_index, scope=scope
        )
        if reasons:
            if covers_entity(assertion, task) and covers_relation(
                assertion, task, governance, scope=scope
            ):
                suppressed[assertion["assertion_id"]] = reasons
            continue
        eligible.append(assertion)

    resolved, conflict_suppressed, unresolved, conflict_trace = resolve_conflicts(
        eligible,
        task,
        governance,
        enabled=cfg.get("use_contradiction_resolver", True),
        use_trust=cfg.get("use_conflict_trust", True),
    )
    suppressed.update(conflict_suppressed)
    admission = admit_actions(
        resolved,
        task,
        governance,
        unresolved,
        enforce_binding=cfg.get("use_action_target_binding", cfg.get("use_workflow_state_binding", True)),
    )
    ranked = sorted(resolved, key=lambda row: _rank(row, task, governance), reverse=True)

    witness_ids = {
        assertion_id
        for ids in admission["support_by_action"].values()
        for assertion_id in ids
    }
    packet_rows = ranked[:top_k]
    packet_ids = {row["assertion_id"] for row in packet_rows}
    for row in ranked:
        if row["assertion_id"] in witness_ids and row["assertion_id"] not in packet_ids:
            packet_rows.append(row)
            packet_ids.add(row["assertion_id"])

    return {
        "decision_evidence": decision_evidence,
        "decision_evidence_completion": completion,
        "decision_scope_relations": scope,
        "assertion_eligible": eligible,
        "resolved_eligible": resolved,
        "packet_assertions": packet_rows,
        "suppression_reasons": suppressed,
        "unresolved_conflicts": unresolved,
        "conflict_trace": conflict_trace,
        **admission,
    }


DECISION_RECORD_FIELDS = (
    "decision_scope_relations",
    "suppression_reasons",
    "unresolved_conflicts",
    "conflict_trace",
    "valid_actions",
    "blocked_actions",
    "blocking_reasons",
    "support_by_action",
    "bindings_consulted",
)


def decision_record(evaluation: dict, *, snapshot_id: str | None = None) -> dict:
    """The deterministic part of a packet: what replay must reproduce exactly.

    Excluded are the pluggable candidate generator's retrieval context and any
    runtime measurement (latency), neither of which the determinism claim
    covers.  Included are the completed evidence identities, every suppression
    reason, the conflict outcome, and each action's decision with the exact
    policy rule and workflow transition consulted.
    """
    record = {
        "decision_evidence_assertion_ids": [
            row["assertion_id"] for row in evaluation.get("decision_evidence", [])
        ],
        "eligible_assertion_ids": [row["assertion_id"] for row in evaluation.get("assertion_eligible", [])],
        "resolved_assertion_ids": [row["assertion_id"] for row in evaluation.get("resolved_eligible", [])],
        "packet_assertion_ids": [row["assertion_id"] for row in evaluation.get("packet_assertions", [])],
        "completion_status": (evaluation.get("decision_evidence_completion") or {}).get("status"),
        "completion_dependency_relations": (evaluation.get("decision_evidence_completion") or {}).get(
            "dependency_relations"
        ),
    }
    for field in DECISION_RECORD_FIELDS:
        record[field] = evaluation.get(field)
    if snapshot_id is not None:
        record["snapshot_id"] = snapshot_id
    return json.loads(canonical_json(record).decode("utf-8"))


def decision_record_digest(evaluation: dict, *, snapshot_id: str | None = None) -> str:
    return hashlib.sha256(canonical_json(decision_record(evaluation, snapshot_id=snapshot_id))).hexdigest()


def snapshot_manifest(data_root: Path) -> dict:
    paths = [
        data_root / "generated" / "assertion_events.jsonl",
        data_root / "generated" / "provenance_activities.jsonl",
        data_root / "config" / "trust_precedence.json",
        data_root / "config" / "source_catalog.json",
        data_root / "config" / "action_registry.json",
        data_root / "config" / "conflict_semantics.json",
        data_root / "ontology" / "ontology_mappings.json",
        *sorted((data_root / "policy").glob("*.json")),
        *sorted((data_root / "workflows").glob("*.json")),
    ]
    file_digests: dict[str, str] = {}
    whole = hashlib.sha256()
    for path in paths:
        if path.suffix == ".jsonl":
            payload = canonical_json(load_jsonl(path))
        else:
            payload = canonical_json(load_json(path))
        digest = hashlib.sha256(payload).hexdigest()
        rel = str(path.relative_to(data_root))
        file_digests[rel] = digest
        whole.update(rel.encode("utf-8"))
        whole.update(b"\0")
        whole.update(payload)
        whole.update(b"\0")
    checkpoint = len(load_jsonl(data_root / "generated" / "assertion_events.jsonl"))
    return {
        "snapshot_id": f"sha256:{whole.hexdigest()}",
        "append_log_checkpoint": checkpoint,
        "file_digests": file_digests,
    }
