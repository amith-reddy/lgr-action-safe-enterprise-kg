# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 357.290 | 2.274 |
| lgr_no_lifecycle_state | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 341.060 | 2.224 |
| lgr_no_record_visibility | 0.710 | 0.870 | 1.000 | 1.000 | 1.000 | 378.020 | 2.224 |
| lgr_no_validity_interval | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 324.240 | 2.269 |
| lgr_no_provenance_activity | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 357.290 | 2.314 |
| lgr_no_source_eligibility | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 357.290 | 2.227 |
| lgr_no_ontology_versioning | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 341.540 | 2.118 |
| lgr_no_policy_versioning | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 336.380 | 2.260 |
| lgr_no_supersession_links | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 332.790 | 2.245 |
| lgr_no_contradiction_resolver | 0.680 | 1.000 | 0.910 | 0.927 | 0.927 | 376.880 | 2.101 |
| lgr_no_conflict_trust | 0.653 | 1.000 | 0.910 | 0.927 | 0.927 | 346.530 | 2.279 |
| lgr_no_workflow_instance_scope | 0.650 | 1.000 | 1.000 | 1.000 | 1.000 | 424.120 | 2.327 |
| lgr_no_action_target_binding | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 | 357.290 | 2.148 |
| lgr_no_bitemporal_checks | 0.733 | 0.870 | 0.980 | 1.000 | 1.000 | 408.960 | 2.243 |
| lgr_no_workflow_scope_or_target_binding | 0.650 | 1.000 | 1.000 | 0.634 | 0.634 | 424.120 | 2.138 |
