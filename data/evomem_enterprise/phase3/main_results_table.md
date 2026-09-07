# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.374 | 0.365 | 0.735 | 1.000 | 1.000 | 440.500 | 18.658 |
| recency_weighted_memory | 0.620 | 0.575 | 0.765 | 1.000 | 1.000 | 281.410 | 1.699 |
| ttl_only_memory | 0.624 | 0.595 | 0.785 | 1.000 | 1.000 | 281.660 | 1.693 |
| temporal_kg_retrieval | 0.654 | 0.565 | 0.930 | 1.000 | 1.000 | 306.330 | 1.624 |
| provenance_aware_kg_query | 0.668 | 0.565 | 0.930 | 1.000 | 1.000 | 380.270 | 1.683 |
| ontology_versioned_retrieval | 0.626 | 0.295 | 0.910 | 1.000 | 1.000 | 471.700 | 1.696 |
| graphrag_style_graph_retrieval | 0.620 | 0.575 | 0.765 | 1.000 | 1.000 | 281.410 | 1.818 |
| event_sourced_latest_state_action | 0.431 | 0.620 | 0.840 | 1.000 | 1.000 | 176.230 | 1.677 |
| lifecycle_governed_kg_retrieval | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 344.620 | 2.281 |
