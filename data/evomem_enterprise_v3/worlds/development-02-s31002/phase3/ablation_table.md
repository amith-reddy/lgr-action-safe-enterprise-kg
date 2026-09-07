# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 344.800 | 2.353 |
| lgr_no_lifecycle_state | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 329.150 | 2.303 |
| lgr_no_record_visibility | 0.716 | 0.850 | 1.000 | 1.000 | 1.000 | 368.730 | 2.320 |
| lgr_no_validity_interval | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 312.940 | 2.219 |
| lgr_no_provenance_activity | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 344.800 | 2.241 |
| lgr_no_source_eligibility | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 344.800 | 2.124 |
| lgr_no_ontology_versioning | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 329.610 | 2.193 |
| lgr_no_policy_versioning | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 324.650 | 2.334 |
| lgr_no_supersession_links | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 321.040 | 2.222 |
| lgr_no_contradiction_resolver | 0.697 | 1.000 | 0.935 | 0.976 | 0.976 | 357.720 | 2.100 |
| lgr_no_conflict_trust | 0.680 | 1.000 | 0.935 | 0.976 | 0.976 | 341.700 | 2.271 |
| lgr_no_workflow_instance_scope | 0.654 | 1.000 | 1.000 | 1.000 | 1.000 | 413.240 | 2.138 |
| lgr_no_action_target_binding | 0.716 | 1.000 | 1.000 | 1.000 | 1.000 | 344.800 | 2.276 |
| lgr_no_bitemporal_checks | 0.763 | 0.850 | 0.970 | 0.976 | 0.976 | 397.920 | 2.310 |
| lgr_no_workflow_scope_or_target_binding | 0.654 | 1.000 | 1.000 | 0.690 | 0.690 | 413.240 | 2.145 |
