# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.375 | 0.380 | 0.740 | 1.000 | 1.000 | 440.870 | 18.743 |
| recency_weighted_memory | 0.617 | 0.550 | 0.755 | 1.000 | 1.000 | 289.270 | 1.629 |
| ttl_only_memory | 0.618 | 0.575 | 0.785 | 1.000 | 1.000 | 289.500 | 1.670 |
| temporal_kg_retrieval | 0.652 | 0.545 | 0.930 | 1.000 | 1.000 | 314.960 | 1.683 |
| provenance_aware_kg_query | 0.667 | 0.545 | 0.925 | 1.000 | 1.000 | 388.270 | 1.654 |
| ontology_versioned_retrieval | 0.629 | 0.290 | 0.910 | 1.000 | 1.000 | 476.900 | 1.672 |
| graphrag_style_graph_retrieval | 0.617 | 0.550 | 0.755 | 1.000 | 1.000 | 289.270 | 1.866 |
| event_sourced_latest_state_action | 0.431 | 0.600 | 0.830 | 1.000 | 1.000 | 178.110 | 1.824 |
| lifecycle_governed_kg_retrieval | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 343.280 | 2.667 |
