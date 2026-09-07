# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 344.620 | 2.328 |
| lgr_no_lifecycle_state | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 328.960 | 2.214 |
| lgr_no_record_visibility | 0.722 | 0.860 | 1.000 | 1.000 | 1.000 | 366.980 | 2.225 |
| lgr_no_validity_interval | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 312.750 | 2.225 |
| lgr_no_provenance_activity | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 344.620 | 2.264 |
| lgr_no_source_eligibility | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 344.620 | 2.352 |
| lgr_no_ontology_versioning | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 329.430 | 2.162 |
| lgr_no_policy_versioning | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 324.470 | 2.208 |
| lgr_no_supersession_links | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 320.750 | 2.260 |
| lgr_no_contradiction_resolver | 0.695 | 1.000 | 0.920 | 0.925 | 0.925 | 361.940 | 2.165 |
| lgr_no_conflict_trust | 0.670 | 1.000 | 0.920 | 0.925 | 0.925 | 336.950 | 2.273 |
| lgr_no_workflow_instance_scope | 0.664 | 1.000 | 1.000 | 1.000 | 1.000 | 409.830 | 2.163 |
| lgr_no_action_target_binding | 0.722 | 1.000 | 1.000 | 1.000 | 1.000 | 344.620 | 2.277 |
| lgr_no_bitemporal_checks | 0.755 | 0.860 | 0.980 | 1.000 | 1.000 | 396.530 | 2.405 |
| lgr_no_workflow_scope_or_target_binding | 0.664 | 1.000 | 1.000 | 0.625 | 0.625 | 409.830 | 2.161 |
