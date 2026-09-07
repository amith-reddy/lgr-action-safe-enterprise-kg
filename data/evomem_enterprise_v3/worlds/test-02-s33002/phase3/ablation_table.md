# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 343.280 | 2.667 |
| lgr_no_lifecycle_state | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 327.700 | 2.345 |
| lgr_no_record_visibility | 0.690 | 0.830 | 1.000 | 1.000 | 1.000 | 370.410 | 2.365 |
| lgr_no_validity_interval | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 311.560 | 2.275 |
| lgr_no_provenance_activity | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 343.280 | 2.104 |
| lgr_no_source_eligibility | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 343.280 | 2.411 |
| lgr_no_ontology_versioning | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 328.160 | 2.281 |
| lgr_no_policy_versioning | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 323.220 | 2.203 |
| lgr_no_supersession_links | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 319.610 | 2.084 |
| lgr_no_contradiction_resolver | 0.667 | 1.000 | 0.920 | 0.950 | 0.950 | 360.510 | 2.197 |
| lgr_no_conflict_trust | 0.647 | 1.000 | 0.920 | 0.950 | 0.950 | 334.070 | 2.244 |
| lgr_no_workflow_instance_scope | 0.632 | 1.000 | 1.000 | 1.000 | 1.000 | 408.460 | 2.036 |
| lgr_no_action_target_binding | 0.690 | 1.000 | 1.000 | 1.000 | 1.000 | 343.280 | 2.292 |
| lgr_no_bitemporal_checks | 0.732 | 0.830 | 0.980 | 0.975 | 0.975 | 402.660 | 2.058 |
| lgr_no_workflow_scope_or_target_binding | 0.632 | 1.000 | 1.000 | 0.575 | 0.575 | 408.460 | 2.367 |
