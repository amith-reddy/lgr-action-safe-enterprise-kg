# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.379 | 0.370 | 0.725 | 1.000 | 1.000 | 440.450 | 20.318 |
| recency_weighted_memory | 0.609 | 0.560 | 0.750 | 1.000 | 1.000 | 294.810 | 1.703 |
| ttl_only_memory | 0.612 | 0.590 | 0.775 | 1.000 | 1.000 | 295.090 | 1.694 |
| temporal_kg_retrieval | 0.644 | 0.555 | 0.935 | 1.000 | 1.000 | 319.700 | 1.660 |
| provenance_aware_kg_query | 0.657 | 0.555 | 0.930 | 1.000 | 1.000 | 397.630 | 1.684 |
| ontology_versioned_retrieval | 0.618 | 0.280 | 0.910 | 1.000 | 1.000 | 493.390 | 1.769 |
| graphrag_style_graph_retrieval | 0.609 | 0.560 | 0.750 | 1.000 | 1.000 | 294.810 | 2.275 |
| event_sourced_latest_state_action | 0.430 | 0.620 | 0.820 | 1.000 | 1.000 | 185.840 | 1.908 |
| lifecycle_governed_kg_retrieval | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 366.990 | 2.318 |
