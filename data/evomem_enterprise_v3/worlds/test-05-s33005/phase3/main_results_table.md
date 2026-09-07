# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.368 | 0.410 | 0.730 | 1.000 | 1.000 | 440.350 | 19.010 |
| recency_weighted_memory | 0.608 | 0.590 | 0.750 | 1.000 | 1.000 | 286.810 | 1.643 |
| ttl_only_memory | 0.611 | 0.625 | 0.765 | 1.000 | 1.000 | 287.120 | 1.689 |
| temporal_kg_retrieval | 0.645 | 0.590 | 0.925 | 1.000 | 1.000 | 311.800 | 1.611 |
| provenance_aware_kg_query | 0.658 | 0.590 | 0.925 | 1.000 | 1.000 | 384.080 | 1.633 |
| ontology_versioned_retrieval | 0.627 | 0.325 | 0.890 | 1.000 | 1.000 | 481.080 | 1.699 |
| graphrag_style_graph_retrieval | 0.608 | 0.590 | 0.750 | 1.000 | 1.000 | 286.810 | 1.848 |
| event_sourced_latest_state_action | 0.437 | 0.645 | 0.830 | 1.000 | 1.000 | 179.510 | 1.669 |
| lifecycle_governed_kg_retrieval | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 357.290 | 2.274 |
