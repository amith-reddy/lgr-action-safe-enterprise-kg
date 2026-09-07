# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 336.520 | 2.213 |
| lgr_no_lifecycle_state | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 321.250 | 2.154 |
| lgr_no_record_visibility | 0.759 | 0.860 | 1.000 | 1.000 | 1.000 | 358.840 | 2.123 |
| lgr_no_validity_interval | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 305.400 | 2.195 |
| lgr_no_provenance_activity | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 336.520 | 2.164 |
| lgr_no_source_eligibility | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 336.520 | 2.040 |
| lgr_no_ontology_versioning | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 321.680 | 2.170 |
| lgr_no_policy_versioning | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 316.830 | 2.167 |
| lgr_no_supersession_links | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 313.200 | 2.299 |
| lgr_no_contradiction_resolver | 0.741 | 1.000 | 0.940 | 0.955 | 0.955 | 346.610 | 2.087 |
| lgr_no_conflict_trust | 0.726 | 1.000 | 0.940 | 0.955 | 0.955 | 330.470 | 2.161 |
| lgr_no_workflow_instance_scope | 0.696 | 1.000 | 1.000 | 1.000 | 1.000 | 408.270 | 2.098 |
| lgr_no_action_target_binding | 0.759 | 1.000 | 1.000 | 1.000 | 1.000 | 336.520 | 2.262 |
| lgr_no_bitemporal_checks | 0.775 | 0.860 | 0.970 | 0.977 | 0.977 | 388.850 | 2.778 |
| lgr_no_workflow_scope_or_target_binding | 0.696 | 1.000 | 1.000 | 0.614 | 0.614 | 408.270 | 2.347 |
