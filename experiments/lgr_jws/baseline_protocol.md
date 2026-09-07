# Baseline information-access protocol

All released retrieval methods read the same immutable assertion snapshot and receive the same task query and initial context budget, `k=8`. Methods differ in their candidate filters and ranking fields. The existing experiment invokes one common LGR decision closure after initial retrieval; action-set equality in that experiment is therefore a gate control, not evidence that one retriever admits actions more accurately.

| Method | Candidate access | Ranking/filter fields | Governance tables during initial retrieval | Final action evaluator |
|---|---|---|---|---|
| Lexical top-k | Full snapshot | lexical query match | none | common LGR gate |
| Recency weighted | Full snapshot | lexical and record time | none | common LGR gate |
| TTL only | Full snapshot | 60-day cutoff | none | common LGR gate |
| Temporal KG | Full snapshot | temporal fields | none | common LGR gate |
| Provenance KG | Full snapshot | temporal and provenance fields | source declarations | common LGR gate |
| Ontology versioned | Full snapshot | ontology mapping | ontology mappings | common LGR gate |
| GraphRAG-style | Full snapshot | entity-seeded graph expansion | none | common LGR gate |
| Event-sourced latest state | Full snapshot | latest record per predicate | none | common LGR gate |
| LGR | Completed decision dependency set | eligibility, trust, conflict, record time | all declared governance tables | LGR gate |

The composed-governance comparator is a separately implemented end-to-end table interpreter. It receives the same snapshot and governance bundle and does not invoke `lgr_operator.py`. Its purpose is to test whether ordinary deterministic composition can reproduce LGR's evidence and decisions, not to serve as a deliberately weakened baseline.

Witnesses added through dependency completion are recorded separately from each method's initial `k=8` context. Token and latency comparisons must state which boundary is measured.
