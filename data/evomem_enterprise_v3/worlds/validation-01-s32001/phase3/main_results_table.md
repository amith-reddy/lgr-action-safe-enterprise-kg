# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.377 | 0.405 | 0.745 | 1.000 | 1.000 | 440.310 | 18.875 |
| recency_weighted_memory | 0.628 | 0.610 | 0.765 | 1.000 | 1.000 | 283.400 | 1.772 |
| ttl_only_memory | 0.628 | 0.625 | 0.785 | 1.000 | 1.000 | 283.570 | 1.679 |
| temporal_kg_retrieval | 0.660 | 0.610 | 0.925 | 1.000 | 1.000 | 309.550 | 1.894 |
| provenance_aware_kg_query | 0.675 | 0.610 | 0.925 | 1.000 | 1.000 | 381.270 | 1.763 |
| ontology_versioned_retrieval | 0.641 | 0.345 | 0.900 | 1.000 | 1.000 | 473.670 | 1.635 |
| graphrag_style_graph_retrieval | 0.628 | 0.610 | 0.765 | 1.000 | 1.000 | 283.400 | 1.777 |
| event_sourced_latest_state_action | 0.464 | 0.655 | 0.830 | 1.000 | 1.000 | 180.790 | 1.777 |
| lifecycle_governed_kg_retrieval | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 358.780 | 2.173 |
