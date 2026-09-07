# Phase 3 Main Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical_top_k_memory | 0.385 | 0.380 | 0.780 | 1.000 | 1.000 | 440.590 | 19.022 |
| recency_weighted_memory | 0.631 | 0.580 | 0.780 | 1.000 | 1.000 | 288.430 | 1.742 |
| ttl_only_memory | 0.635 | 0.605 | 0.815 | 1.000 | 1.000 | 288.710 | 1.768 |
| temporal_kg_retrieval | 0.652 | 0.575 | 0.935 | 1.000 | 1.000 | 322.120 | 1.861 |
| provenance_aware_kg_query | 0.664 | 0.575 | 0.930 | 1.000 | 1.000 | 398.660 | 1.692 |
| ontology_versioned_retrieval | 0.623 | 0.295 | 0.905 | 1.000 | 1.000 | 493.310 | 1.704 |
| graphrag_style_graph_retrieval | 0.631 | 0.580 | 0.780 | 1.000 | 1.000 | 288.430 | 1.774 |
| event_sourced_latest_state_action | 0.450 | 0.625 | 0.840 | 1.000 | 1.000 | 186.660 | 1.776 |
| lifecycle_governed_kg_retrieval | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 368.460 | 2.221 |
