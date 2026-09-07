# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.387 | 0.360 | 0.765 | 1.000 | 1.000 | 440.580 | 18.320 |
| recency_weighted_memory | 0.641 | 0.570 | 0.775 | 1.000 | 1.000 | 281.410 | 1.621 |
| ttl_only_memory | 0.643 | 0.585 | 0.795 | 1.000 | 1.000 | 281.530 | 1.676 |
| temporal_kg_retrieval | 0.688 | 0.570 | 0.945 | 1.000 | 1.000 | 303.900 | 1.672 |
| provenance_aware_kg_query | 0.703 | 0.570 | 0.945 | 1.000 | 1.000 | 374.110 | 1.650 |
| ontology_versioned_retrieval | 0.658 | 0.295 | 0.920 | 1.000 | 1.000 | 468.230 | 1.728 |
| graphrag_style_graph_retrieval | 0.641 | 0.570 | 0.775 | 1.000 | 1.000 | 281.410 | 1.788 |
| event_sourced_latest_state_action | 0.456 | 0.635 | 0.840 | 1.000 | 1.000 | 176.200 | 1.661 |
| lifecycle_governed_kg_retrieval | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 336.520 | 2.213 |
