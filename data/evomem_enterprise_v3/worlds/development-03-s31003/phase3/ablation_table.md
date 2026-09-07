# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 346.220 | 2.293 |
| lgr_no_lifecycle_state | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 330.510 | 2.298 |
| lgr_no_record_visibility | 0.705 | 0.840 | 1.000 | 1.000 | 1.000 | 371.740 | 2.261 |
| lgr_no_validity_interval | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 314.220 | 2.371 |
| lgr_no_provenance_activity | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 346.220 | 2.164 |
| lgr_no_source_eligibility | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 346.220 | 2.270 |
| lgr_no_ontology_versioning | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 330.960 | 2.303 |
| lgr_no_policy_versioning | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 325.990 | 2.446 |
| lgr_no_supersession_links | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 322.620 | 2.139 |
| lgr_no_contradiction_resolver | 0.676 | 1.000 | 0.910 | 0.929 | 0.929 | 367.930 | 2.571 |
| lgr_no_conflict_trust | 0.647 | 1.000 | 0.910 | 0.929 | 0.929 | 336.980 | 2.209 |
| lgr_no_workflow_instance_scope | 0.643 | 1.000 | 1.000 | 1.000 | 1.000 | 414.770 | 2.144 |
| lgr_no_action_target_binding | 0.705 | 1.000 | 1.000 | 1.000 | 1.000 | 346.220 | 2.962 |
| lgr_no_bitemporal_checks | 0.741 | 0.840 | 0.980 | 0.976 | 0.976 | 405.220 | 3.108 |
| lgr_no_workflow_scope_or_target_binding | 0.643 | 1.000 | 1.000 | 0.667 | 0.667 | 414.770 | 2.342 |
