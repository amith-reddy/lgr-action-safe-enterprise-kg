# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 366.940 | 2.211 |
| lgr_no_lifecycle_state | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 350.270 | 2.196 |
| lgr_no_record_visibility | 0.711 | 0.860 | 1.000 | 1.000 | 1.000 | 389.300 | 2.237 |
| lgr_no_validity_interval | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 333.030 | 2.234 |
| lgr_no_provenance_activity | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 366.940 | 2.257 |
| lgr_no_source_eligibility | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 366.940 | 2.152 |
| lgr_no_ontology_versioning | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 350.770 | 2.605 |
| lgr_no_policy_versioning | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 345.540 | 2.427 |
| lgr_no_supersession_links | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 341.880 | 2.316 |
| lgr_no_contradiction_resolver | 0.686 | 1.000 | 0.920 | 0.933 | 0.933 | 383.360 | 2.664 |
| lgr_no_conflict_trust | 0.663 | 1.000 | 0.920 | 0.933 | 0.933 | 357.650 | 2.455 |
| lgr_no_workflow_instance_scope | 0.647 | 1.000 | 1.000 | 1.000 | 1.000 | 440.390 | 2.254 |
| lgr_no_action_target_binding | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 366.940 | 2.424 |
| lgr_no_bitemporal_checks | 0.733 | 0.860 | 0.970 | 0.978 | 0.978 | 422.310 | 2.205 |
| lgr_no_workflow_scope_or_target_binding | 0.647 | 1.000 | 1.000 | 0.600 | 0.600 | 440.390 | 2.259 |
