# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.365 | 0.390 | 0.750 | 1.000 | 1.000 | 440.460 | 18.845 |
| recency_weighted_memory | 0.604 | 0.595 | 0.770 | 1.000 | 1.000 | 286.490 | 1.684 |
| ttl_only_memory | 0.606 | 0.610 | 0.800 | 1.000 | 1.000 | 286.710 | 1.711 |
| temporal_kg_retrieval | 0.635 | 0.590 | 0.935 | 1.000 | 1.000 | 314.980 | 1.645 |
| provenance_aware_kg_query | 0.651 | 0.590 | 0.930 | 1.000 | 1.000 | 387.420 | 1.767 |
| ontology_versioned_retrieval | 0.616 | 0.310 | 0.900 | 1.000 | 1.000 | 485.540 | 1.721 |
| graphrag_style_graph_retrieval | 0.604 | 0.595 | 0.770 | 1.000 | 1.000 | 286.490 | 1.818 |
| event_sourced_latest_state_action | 0.425 | 0.635 | 0.830 | 1.000 | 1.000 | 180.710 | 1.704 |
| lifecycle_governed_kg_retrieval | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 362.120 | 2.214 |
