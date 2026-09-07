# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.379 | 0.385 | 0.755 | 1.000 | 1.000 | 440.550 | 18.676 |
| recency_weighted_memory | 0.611 | 0.565 | 0.765 | 1.000 | 1.000 | 288.520 | 1.698 |
| ttl_only_memory | 0.615 | 0.595 | 0.795 | 1.000 | 1.000 | 288.790 | 1.791 |
| temporal_kg_retrieval | 0.644 | 0.565 | 0.940 | 1.000 | 1.000 | 318.200 | 1.667 |
| provenance_aware_kg_query | 0.659 | 0.565 | 0.935 | 1.000 | 1.000 | 391.540 | 1.699 |
| ontology_versioned_retrieval | 0.624 | 0.295 | 0.905 | 1.000 | 1.000 | 487.940 | 1.721 |
| graphrag_style_graph_retrieval | 0.611 | 0.565 | 0.765 | 1.000 | 1.000 | 288.520 | 1.816 |
| event_sourced_latest_state_action | 0.436 | 0.610 | 0.825 | 1.000 | 1.000 | 183.920 | 1.719 |
| lifecycle_governed_kg_retrieval | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 360.820 | 2.255 |
