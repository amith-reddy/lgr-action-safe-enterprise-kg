# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 366.990 | 2.318 |
| lgr_no_lifecycle_state | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 350.350 | 2.488 |
| lgr_no_record_visibility | 0.698 | 0.860 | 1.000 | 1.000 | 1.000 | 389.350 | 2.246 |
| lgr_no_validity_interval | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 333.070 | 2.244 |
| lgr_no_provenance_activity | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 366.990 | 2.404 |
| lgr_no_source_eligibility | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 366.990 | 2.297 |
| lgr_no_ontology_versioning | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 350.820 | 2.276 |
| lgr_no_policy_versioning | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 345.590 | 2.235 |
| lgr_no_supersession_links | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 341.720 | 2.280 |
| lgr_no_contradiction_resolver | 0.682 | 1.000 | 0.925 | 0.976 | 0.976 | 380.430 | 2.084 |
| lgr_no_conflict_trust | 0.667 | 1.000 | 0.925 | 0.976 | 0.976 | 360.880 | 2.524 |
| lgr_no_workflow_instance_scope | 0.639 | 1.000 | 1.000 | 1.000 | 1.000 | 433.820 | 2.198 |
| lgr_no_action_target_binding | 0.698 | 1.000 | 1.000 | 1.000 | 1.000 | 366.990 | 2.104 |
| lgr_no_bitemporal_checks | 0.726 | 0.860 | 0.970 | 0.976 | 0.976 | 422.480 | 2.349 |
| lgr_no_workflow_scope_or_target_binding | 0.639 | 1.000 | 1.000 | 0.659 | 0.659 | 433.820 | 2.127 |
