# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 358.780 | 2.173 |
| lgr_no_lifecycle_state | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 342.490 | 2.106 |
| lgr_no_record_visibility | 0.748 | 0.890 | 1.000 | 1.000 | 1.000 | 376.330 | 2.188 |
| lgr_no_validity_interval | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 325.600 | 2.354 |
| lgr_no_provenance_activity | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 358.780 | 2.161 |
| lgr_no_source_eligibility | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 358.780 | 2.195 |
| lgr_no_ontology_versioning | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 342.960 | 2.064 |
| lgr_no_policy_versioning | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 337.790 | 2.253 |
| lgr_no_supersession_links | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 334.150 | 2.181 |
| lgr_no_contradiction_resolver | 0.721 | 1.000 | 0.925 | 0.955 | 0.955 | 372.370 | 2.106 |
| lgr_no_conflict_trust | 0.698 | 1.000 | 0.925 | 0.955 | 0.955 | 349.540 | 2.285 |
| lgr_no_workflow_instance_scope | 0.684 | 1.000 | 1.000 | 1.000 | 1.000 | 430.280 | 2.198 |
| lgr_no_action_target_binding | 0.748 | 1.000 | 1.000 | 1.000 | 1.000 | 358.780 | 2.066 |
| lgr_no_bitemporal_checks | 0.762 | 0.890 | 0.980 | 0.977 | 0.977 | 397.480 | 2.566 |
| lgr_no_workflow_scope_or_target_binding | 0.684 | 1.000 | 1.000 | 0.659 | 0.659 | 430.280 | 4.098 |
