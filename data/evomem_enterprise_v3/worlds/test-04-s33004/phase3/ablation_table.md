# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 376.540 | 2.273 |
| lgr_no_lifecycle_state | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 359.440 | 2.236 |
| lgr_no_record_visibility | 0.738 | 0.900 | 1.000 | 1.000 | 1.000 | 392.500 | 2.262 |
| lgr_no_validity_interval | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 341.740 | 2.220 |
| lgr_no_provenance_activity | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 376.540 | 2.276 |
| lgr_no_source_eligibility | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 376.540 | 2.294 |
| lgr_no_ontology_versioning | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 359.950 | 2.153 |
| lgr_no_policy_versioning | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 354.620 | 2.405 |
| lgr_no_supersession_links | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 350.490 | 2.345 |
| lgr_no_contradiction_resolver | 0.718 | 1.000 | 0.930 | 0.953 | 0.953 | 386.380 | 2.119 |
| lgr_no_conflict_trust | 0.702 | 1.000 | 0.930 | 0.953 | 0.953 | 368.850 | 2.311 |
| lgr_no_workflow_instance_scope | 0.678 | 1.000 | 1.000 | 1.000 | 1.000 | 446.840 | 2.301 |
| lgr_no_action_target_binding | 0.738 | 1.000 | 1.000 | 1.000 | 1.000 | 376.540 | 2.139 |
| lgr_no_bitemporal_checks | 0.747 | 0.900 | 0.990 | 1.000 | 1.000 | 409.440 | 2.372 |
| lgr_no_workflow_scope_or_target_binding | 0.678 | 1.000 | 1.000 | 0.674 | 0.674 | 446.840 | 2.154 |
