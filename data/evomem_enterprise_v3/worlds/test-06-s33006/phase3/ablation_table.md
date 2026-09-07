# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 362.120 | 2.214 |
| lgr_no_lifecycle_state | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 345.650 | 2.386 |
| lgr_no_record_visibility | 0.728 | 0.890 | 1.000 | 1.000 | 1.000 | 379.650 | 2.344 |
| lgr_no_validity_interval | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 328.640 | 2.385 |
| lgr_no_provenance_activity | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 362.120 | 2.368 |
| lgr_no_source_eligibility | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 362.120 | 2.409 |
| lgr_no_ontology_versioning | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 346.160 | 2.393 |
| lgr_no_policy_versioning | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 340.950 | 2.420 |
| lgr_no_supersession_links | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 337.240 | 2.278 |
| lgr_no_contradiction_resolver | 0.698 | 1.000 | 0.915 | 0.927 | 0.927 | 383.230 | 2.054 |
| lgr_no_conflict_trust | 0.671 | 1.000 | 0.915 | 0.927 | 0.927 | 356.050 | 2.253 |
| lgr_no_workflow_instance_scope | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 428.870 | 2.370 |
| lgr_no_action_target_binding | 0.728 | 1.000 | 1.000 | 1.000 | 1.000 | 362.120 | 2.041 |
| lgr_no_bitemporal_checks | 0.747 | 0.890 | 0.990 | 0.976 | 0.976 | 399.200 | 2.335 |
| lgr_no_workflow_scope_or_target_binding | 0.667 | 1.000 | 1.000 | 0.634 | 0.634 | 428.870 | 2.100 |
