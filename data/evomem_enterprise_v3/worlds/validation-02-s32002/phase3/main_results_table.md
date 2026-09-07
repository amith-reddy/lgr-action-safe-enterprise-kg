# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.367 | 0.410 | 0.735 | 1.000 | 1.000 | 440.800 | 18.803 |
| recency_weighted_memory | 0.620 | 0.590 | 0.750 | 1.000 | 1.000 | 280.800 | 1.708 |
| ttl_only_memory | 0.622 | 0.610 | 0.780 | 1.000 | 1.000 | 280.990 | 1.725 |
| temporal_kg_retrieval | 0.656 | 0.590 | 0.925 | 1.000 | 1.000 | 305.580 | 1.653 |
| provenance_aware_kg_query | 0.670 | 0.590 | 0.920 | 1.000 | 1.000 | 376.200 | 1.714 |
| ontology_versioned_retrieval | 0.634 | 0.345 | 0.895 | 1.000 | 1.000 | 462.140 | 1.687 |
| graphrag_style_graph_retrieval | 0.620 | 0.590 | 0.750 | 1.000 | 1.000 | 280.800 | 1.833 |
| event_sourced_latest_state_action | 0.449 | 0.650 | 0.825 | 1.000 | 1.000 | 174.230 | 1.686 |
| lifecycle_governed_kg_retrieval | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 338.420 | 2.165 |
