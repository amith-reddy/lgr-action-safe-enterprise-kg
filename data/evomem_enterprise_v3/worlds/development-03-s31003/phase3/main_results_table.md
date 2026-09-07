# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.377 | 0.440 | 0.745 | 1.000 | 1.000 | 440.660 | 18.626 |
| recency_weighted_memory | 0.627 | 0.585 | 0.745 | 1.000 | 1.000 | 287.900 | 1.702 |
| ttl_only_memory | 0.631 | 0.615 | 0.780 | 1.000 | 1.000 | 288.190 | 1.704 |
| temporal_kg_retrieval | 0.666 | 0.580 | 0.915 | 1.000 | 1.000 | 314.300 | 1.644 |
| provenance_aware_kg_query | 0.679 | 0.580 | 0.910 | 1.000 | 1.000 | 388.320 | 1.705 |
| ontology_versioned_retrieval | 0.650 | 0.345 | 0.885 | 1.000 | 1.000 | 474.860 | 1.762 |
| graphrag_style_graph_retrieval | 0.627 | 0.585 | 0.745 | 1.000 | 1.000 | 287.900 | 1.798 |
| event_sourced_latest_state_action | 0.463 | 0.625 | 0.825 | 1.000 | 1.000 | 180.070 | 1.694 |
| lifecycle_governed_kg_retrieval | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 346.220 | 2.293 |
