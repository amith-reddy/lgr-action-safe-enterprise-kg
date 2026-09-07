# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 360.820 | 2.255 |
| lgr_no_lifecycle_state | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 344.440 | 2.253 |
| lgr_no_record_visibility | 0.702 | 0.860 | 1.000 | 1.000 | 1.000 | 383.140 | 2.313 |
| lgr_no_validity_interval | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 327.460 | 2.273 |
| lgr_no_provenance_activity | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 360.820 | 2.251 |
| lgr_no_source_eligibility | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 360.820 | 2.106 |
| lgr_no_ontology_versioning | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 344.930 | 2.237 |
| lgr_no_policy_versioning | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 339.760 | 2.291 |
| lgr_no_supersession_links | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 335.910 | 2.299 |
| lgr_no_contradiction_resolver | 0.684 | 1.000 | 0.935 | 0.976 | 0.976 | 371.340 | 2.121 |
| lgr_no_conflict_trust | 0.667 | 1.000 | 0.935 | 0.976 | 0.976 | 353.110 | 2.332 |
| lgr_no_workflow_instance_scope | 0.642 | 1.000 | 1.000 | 1.000 | 1.000 | 429.300 | 2.322 |
| lgr_no_action_target_binding | 0.702 | 1.000 | 1.000 | 1.000 | 1.000 | 360.820 | 2.155 |
| lgr_no_bitemporal_checks | 0.729 | 0.860 | 0.990 | 0.976 | 0.976 | 403.930 | 2.302 |
| lgr_no_workflow_scope_or_target_binding | 0.642 | 1.000 | 1.000 | 0.667 | 0.667 | 429.300 | 2.193 |
