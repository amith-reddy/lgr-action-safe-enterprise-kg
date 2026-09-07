# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 346.710 | 2.107 |
| lgr_no_lifecycle_state | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 330.990 | 2.088 |
| lgr_no_record_visibility | 0.663 | 0.840 | 1.000 | 1.000 | 1.000 | 372.250 | 2.118 |
| lgr_no_validity_interval | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 314.680 | 2.122 |
| lgr_no_provenance_activity | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 346.710 | 2.162 |
| lgr_no_source_eligibility | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 346.710 | 2.026 |
| lgr_no_ontology_versioning | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 331.450 | 2.130 |
| lgr_no_policy_versioning | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 326.470 | 2.150 |
| lgr_no_supersession_links | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 322.780 | 2.166 |
| lgr_no_contradiction_resolver | 0.642 | 1.000 | 0.915 | 0.944 | 0.944 | 363.880 | 2.021 |
| lgr_no_conflict_trust | 0.620 | 1.000 | 0.915 | 0.944 | 0.944 | 337.500 | 2.224 |
| lgr_no_workflow_instance_scope | 0.611 | 1.000 | 1.000 | 1.000 | 1.000 | 405.410 | 2.232 |
| lgr_no_action_target_binding | 0.663 | 1.000 | 1.000 | 1.000 | 1.000 | 346.710 | 2.025 |
| lgr_no_bitemporal_checks | 0.714 | 0.840 | 0.980 | 0.972 | 0.972 | 402.780 | 2.175 |
| lgr_no_workflow_scope_or_target_binding | 0.611 | 1.000 | 1.000 | 0.583 | 0.583 | 405.410 | 2.042 |
