# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 338.420 | 2.165 |
| lgr_no_lifecycle_state | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 323.060 | 2.221 |
| lgr_no_record_visibility | 0.723 | 0.860 | 1.000 | 1.000 | 1.000 | 360.740 | 2.252 |
| lgr_no_validity_interval | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 307.150 | 2.226 |
| lgr_no_provenance_activity | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 338.420 | 2.260 |
| lgr_no_source_eligibility | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 338.420 | 2.211 |
| lgr_no_ontology_versioning | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 323.510 | 2.023 |
| lgr_no_policy_versioning | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 318.570 | 2.257 |
| lgr_no_supersession_links | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 315.200 | 2.176 |
| lgr_no_contradiction_resolver | 0.694 | 1.000 | 0.915 | 0.951 | 0.951 | 359.020 | 2.026 |
| lgr_no_conflict_trust | 0.670 | 1.000 | 0.915 | 0.951 | 0.951 | 332.340 | 2.345 |
| lgr_no_workflow_instance_scope | 0.661 | 1.000 | 1.000 | 1.000 | 1.000 | 405.030 | 2.258 |
| lgr_no_action_target_binding | 0.723 | 1.000 | 1.000 | 1.000 | 1.000 | 338.420 | 2.070 |
| lgr_no_bitemporal_checks | 0.751 | 0.860 | 0.970 | 1.000 | 1.000 | 392.070 | 2.208 |
| lgr_no_workflow_scope_or_target_binding | 0.661 | 1.000 | 1.000 | 0.659 | 0.659 | 405.030 | 2.068 |
