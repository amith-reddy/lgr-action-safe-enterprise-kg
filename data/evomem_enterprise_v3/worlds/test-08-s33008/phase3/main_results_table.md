# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.387 | 0.410 | 0.730 | 1.000 | 1.000 | 440.660 | 18.753 |
| recency_weighted_memory | 0.622 | 0.580 | 0.740 | 1.000 | 1.000 | 298.220 | 1.660 |
| ttl_only_memory | 0.626 | 0.610 | 0.770 | 1.000 | 1.000 | 298.510 | 1.707 |
| temporal_kg_retrieval | 0.662 | 0.575 | 0.925 | 1.000 | 1.000 | 323.130 | 1.637 |
| provenance_aware_kg_query | 0.671 | 0.575 | 0.920 | 1.000 | 1.000 | 400.880 | 1.684 |
| ontology_versioned_retrieval | 0.643 | 0.315 | 0.890 | 1.000 | 1.000 | 495.740 | 1.703 |
| graphrag_style_graph_retrieval | 0.622 | 0.580 | 0.740 | 1.000 | 1.000 | 298.220 | 1.804 |
| event_sourced_latest_state_action | 0.475 | 0.645 | 0.815 | 1.000 | 1.000 | 188.540 | 1.672 |
| lifecycle_governed_kg_retrieval | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 366.940 | 2.211 |
