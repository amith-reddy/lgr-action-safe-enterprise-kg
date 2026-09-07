# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.357 | 0.355 | 0.735 | 1.000 | 1.000 | 440.900 | 18.448 |
| recency_weighted_memory | 0.593 | 0.555 | 0.755 | 1.000 | 1.000 | 286.100 | 1.692 |
| ttl_only_memory | 0.595 | 0.570 | 0.775 | 1.000 | 1.000 | 286.260 | 1.655 |
| temporal_kg_retrieval | 0.625 | 0.550 | 0.925 | 1.000 | 1.000 | 311.090 | 1.589 |
| provenance_aware_kg_query | 0.638 | 0.550 | 0.920 | 1.000 | 1.000 | 384.240 | 1.682 |
| ontology_versioned_retrieval | 0.605 | 0.285 | 0.885 | 1.000 | 1.000 | 481.240 | 1.672 |
| graphrag_style_graph_retrieval | 0.593 | 0.555 | 0.755 | 1.000 | 1.000 | 286.100 | 1.756 |
| event_sourced_latest_state_action | 0.396 | 0.600 | 0.820 | 1.000 | 1.000 | 175.640 | 1.586 |
| lifecycle_governed_kg_retrieval | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 346.710 | 2.107 |
