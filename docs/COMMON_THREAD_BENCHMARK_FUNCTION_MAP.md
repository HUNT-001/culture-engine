# CommonThreadBench v2 — Production functions exercised, per test file

Measured, not asserted: each `tests/test_bench_*.py` file was run under `coverage` and executed lines were mapped onto production function bodies (`python -m bench.function_map`). ✓ = a line of the function's own body ran. Import-time execution does not count.

| Production function | baseline_guard | constraints | evidence | faults | human_eval | live_resolution | metrics | qloo_shape | ranking | report | resolution | scenarios |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `providers/qloo.py` · `QlooClient._get_json` | · | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | ✓ | ✓ | ✓ | · |
| `providers/qloo.py` · `QlooClient._result_list` | · | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | ✓ | ✓ | ✓ | · |
| `providers/qloo.py` · `QlooClient._entity_subtype` | · | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | ✓ | ✓ | ✓ | · |
| `providers/qloo.py` · `QlooClient._extract_explanation` | · | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | ✓ | ✓ | ✓ | · |
| `providers/qloo.py` · `QlooClient.search_entities` | · | · | · | ✓ | · | ✓ | · | ✓ | · | ✓ | ✓ | · |
| `providers/qloo.py` · `QlooClient.get_place_recommendations` | · | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | ✓ | ✓ | ✓ | · |
| `services/resolution.py` · `confirmed_index` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/resolution.py` · `normalize_name` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.resolve_entities` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.retrieve_insights` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.normalize_candidates` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.rank_options` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.validate_evidence` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.compose_response` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `workflows/nodes.py` · `build_nodes.validate_output` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `merge_candidate_batches` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `apply_hard_constraints` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `rank_candidates` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `select_options` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `_affinity_of` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/ranking.py` · `_affinity_bounds` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/evidence.py` · `build_interest_index` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/evidence.py` · `matched_interest_names` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `services/provenance.py` · `validate_and_label_options` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `providers/composer.py` · `DeterministicComposer.compose` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | · |
| `providers/mock_qloo.py` · `MockQlooClient.get_place_recommendations` | · | · | ✓ | · | · | · | · | · | · | ✓ | · | · |
| `api/routes/recommendations.py` · `execute_workflow` | · | · | · | ✓ | · | · | · | · | · | ✓ | · | · |
| `api/routes/entities.py` · `search_entities` | · | · | · | ✓ | · | · | · | · | · | ✓ | ✓ | · |
| `api/routes/plans.py` · `run_plan_recommendations` | · | · | · | ✓ | · | · | · | · | · | · | · | · |
| `api/routes/plans.py` · `create_plan` | · | · | · | ✓ | · | · | · | · | · | · | · | · |
| `domain/schemas.py` · `RecommendationRequest.check_unique_participants` | · | ✓ | ✓ | ✓ | · | ✓ | · | · | ✓ | ✓ | ✓ | ✓ |

**Test files that execute none of the listed behavioural functions:** `test_bench_baseline_guard.py`, `test_bench_human_eval.py`, `test_bench_metrics.py`. `test_bench_metrics` and `test_bench_human_eval` verify metric arithmetic and the human-study protocol, which says nothing about the product. `test_bench_baseline_guard` inspects route registration and symbol presence on the live app object without running the pipeline.

**Listed production functions never executed by any benchmark test:** none.
