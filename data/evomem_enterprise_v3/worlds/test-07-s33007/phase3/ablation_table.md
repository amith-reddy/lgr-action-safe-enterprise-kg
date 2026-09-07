# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 368.460 | 2.221 |
| lgr_no_lifecycle_state | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 351.710 | 2.269 |
| lgr_no_record_visibility | 0.741 | 0.880 | 1.000 | 1.000 | 1.000 | 387.620 | 2.200 |
| lgr_no_validity_interval | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 334.360 | 2.333 |
| lgr_no_provenance_activity | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 368.460 | 2.320 |
| lgr_no_source_eligibility | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 368.460 | 2.089 |
| lgr_no_ontology_versioning | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 352.220 | 2.200 |
| lgr_no_policy_versioning | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 346.900 | 2.254 |
| lgr_no_supersession_links | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 343.060 | 2.186 |
| lgr_no_contradiction_resolver | 0.714 | 1.000 | 0.915 | 0.957 | 0.957 | 386.110 | 2.303 |
| lgr_no_conflict_trust | 0.688 | 1.000 | 0.915 | 0.957 | 0.957 | 359.280 | 2.294 |
| lgr_no_workflow_instance_scope | 0.674 | 1.000 | 1.000 | 1.000 | 1.000 | 443.490 | 2.081 |
| lgr_no_action_target_binding | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 368.460 | 2.233 |
| lgr_no_bitemporal_checks | 0.776 | 0.880 | 0.990 | 1.000 | 1.000 | 404.830 | 2.222 |
| lgr_no_workflow_scope_or_target_binding | 0.674 | 1.000 | 1.000 | 0.674 | 0.674 | 443.490 | 2.374 |
