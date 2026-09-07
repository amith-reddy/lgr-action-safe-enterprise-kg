# Phase 3 LGR Ablation Test Results

| Method | eligible_f1 | stale_suppression_recall | contradiction_loser_suppression_recall | action_exact_match_action_only | llm_selected_action_valid_accuracy_action_only | token_count_estimate | retrieval_latency_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lifecycle_governed_kg_retrieval | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 362.250 | 2.237 |
| lgr_no_lifecycle_state | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 345.810 | 2.257 |
| lgr_no_record_visibility | 0.781 | 0.910 | 1.000 | 1.000 | 1.000 | 376.580 | 2.286 |
| lgr_no_validity_interval | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 328.780 | 2.263 |
| lgr_no_provenance_activity | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 362.250 | 2.228 |
| lgr_no_source_eligibility | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 362.250 | 2.143 |
| lgr_no_ontology_versioning | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 346.290 | 2.311 |
| lgr_no_policy_versioning | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 341.060 | 2.263 |
| lgr_no_supersession_links | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 337.430 | 2.165 |
| lgr_no_contradiction_resolver | 0.750 | 1.000 | 0.910 | 0.936 | 0.936 | 384.770 | 2.286 |
| lgr_no_conflict_trust | 0.722 | 1.000 | 0.910 | 0.936 | 0.936 | 354.440 | 2.274 |
| lgr_no_workflow_instance_scope | 0.711 | 1.000 | 1.000 | 1.000 | 1.000 | 438.890 | 2.188 |
| lgr_no_action_target_binding | 0.781 | 1.000 | 1.000 | 1.000 | 1.000 | 362.250 | 2.399 |
| lgr_no_bitemporal_checks | 0.779 | 0.910 | 0.990 | 0.979 | 0.979 | 393.780 | 2.214 |
| lgr_no_workflow_scope_or_target_binding | 0.711 | 1.000 | 1.000 | 0.596 | 0.596 | 438.890 | 2.407 |
