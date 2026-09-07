# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.380 | 0.350 | 0.760 | 1.000 | 1.000 | 440.680 | 18.747 |
| recency_weighted_memory | 0.637 | 0.560 | 0.775 | 1.000 | 1.000 | 284.220 | 1.696 |
| ttl_only_memory | 0.639 | 0.570 | 0.800 | 1.000 | 1.000 | 284.300 | 1.656 |
| temporal_kg_retrieval | 0.663 | 0.560 | 0.935 | 1.000 | 1.000 | 311.920 | 1.693 |
| provenance_aware_kg_query | 0.675 | 0.560 | 0.930 | 1.000 | 1.000 | 385.510 | 1.667 |
| ontology_versioned_retrieval | 0.634 | 0.290 | 0.905 | 1.000 | 1.000 | 477.110 | 1.749 |
| graphrag_style_graph_retrieval | 0.637 | 0.560 | 0.775 | 1.000 | 1.000 | 284.220 | 1.899 |
| event_sourced_latest_state_action | 0.461 | 0.630 | 0.825 | 1.000 | 1.000 | 180.610 | 1.668 |
| lifecycle_governed_kg_retrieval | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 344.800 | 2.353 |
