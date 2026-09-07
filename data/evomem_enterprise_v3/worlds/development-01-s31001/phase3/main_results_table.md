# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.377 | 0.435 | 0.765 | 1.000 | 1.000 | 440.730 | 18.885 |
| recency_weighted_memory | 0.626 | 0.625 | 0.750 | 1.000 | 1.000 | 289.550 | 1.680 |
| ttl_only_memory | 0.629 | 0.645 | 0.780 | 1.000 | 1.000 | 289.710 | 1.706 |
| temporal_kg_retrieval | 0.660 | 0.620 | 0.910 | 1.000 | 1.000 | 316.060 | 1.691 |
| provenance_aware_kg_query | 0.673 | 0.620 | 0.905 | 1.000 | 1.000 | 390.760 | 1.695 |
| ontology_versioned_retrieval | 0.638 | 0.355 | 0.875 | 1.000 | 1.000 | 485.900 | 1.714 |
| graphrag_style_graph_retrieval | 0.626 | 0.625 | 0.750 | 1.000 | 1.000 | 289.550 | 1.818 |
| event_sourced_latest_state_action | 0.451 | 0.665 | 0.825 | 1.000 | 1.000 | 181.520 | 1.724 |
| lifecycle_governed_kg_retrieval | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 362.250 | 2.237 |
