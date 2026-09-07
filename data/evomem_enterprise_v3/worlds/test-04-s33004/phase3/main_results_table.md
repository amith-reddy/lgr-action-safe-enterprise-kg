# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.378 | 0.375 | 0.760 | 1.000 | 1.000 | 440.530 | 18.810 |
| recency_weighted_memory | 0.608 | 0.590 | 0.770 | 1.000 | 1.000 | 289.300 | 1.740 |
| ttl_only_memory | 0.612 | 0.620 | 0.805 | 1.000 | 1.000 | 289.590 | 1.717 |
| temporal_kg_retrieval | 0.640 | 0.585 | 0.935 | 1.000 | 1.000 | 320.000 | 1.605 |
| provenance_aware_kg_query | 0.655 | 0.585 | 0.930 | 1.000 | 1.000 | 394.820 | 1.686 |
| ontology_versioned_retrieval | 0.618 | 0.295 | 0.895 | 1.000 | 1.000 | 497.690 | 1.685 |
| graphrag_style_graph_retrieval | 0.608 | 0.590 | 0.770 | 1.000 | 1.000 | 289.300 | 1.851 |
| event_sourced_latest_state_action | 0.431 | 0.620 | 0.840 | 1.000 | 1.000 | 186.110 | 1.722 |
| lifecycle_governed_kg_retrieval | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 376.540 | 2.273 |
