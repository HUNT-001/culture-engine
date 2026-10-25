# CommonThreadBench v2 — Results (offline, production-linked)

*Benchmark version* `2.0` · *required application checkpoint* `746ee952f7569d630f0a4488e5f75e6ece432060` · regenerate with `python -m bench.run_benchmark`.

> **Read this first.** Every number below carries a provenance tag. No number comes from a live request or a human study. Fixtures are synthetic; "mocked-integration" means the real adapter, workflow and routes ran against Qloo-shaped mock HTTP, **not** the real Qloo service. v1 figures (9.3%, 55.6%, 50%, 100%) were measured against a stale revision and mostly against the benchmark's own fixtures; they are historical and are **not** reproduced here (see `docs/benchmark-history/`).

| Tag | Meaning |
|---|---|
| `synthetic-arithmetic` | benchmark-side arithmetic on synthetic inputs; checks metric maths only |
| `production-function` | a real production function called with synthetic inputs |
| `mocked-integration` | real adapter/workflow/routes over mock HTTP fixtures; not the real Qloo service |
| `live-request` | a request that reached the live Qloo API (none in v2) |
| `human-study` | ratings from real participants (none collected yet) |

## 0. Baseline guard

- HEAD descends from the required checkpoint: **True**
- Production routes registered (from the live app's OpenAPI): 8/8
- Production features present: 8/8

Dataset: 48 scenarios, 16 development / 32 held-out. Reporting only; nothing in v2 was tuned, and no production weight, policy or configuration was changed.

## 1. Entity resolution — `mocked-integration`

Real `QlooClient` + real `resolve_entities` over mock `/search`. Gold: *synthetic ids; author-written; not human-verified; not live-verified*. **n = 13**, so these rates are indicative only.

| Subset | False automatic confirmation | Auto-confirm precision | Abstain rate | Unacceptable outcomes |
|---|---|---|---|---|
| All | 2/11 (18.2%) | 7/9 (77.8%) | 3/12 (25.0%) | 2/13 (15.4%) |
| Development | 1/7 (14.3%) | 4/5 (80.0%) | 3/8 (37.5%) | 1/9 (11.1%) |
| Held-out | 1/4 (25.0%) | 3/4 (75.0%) | 0/4 (0.0%) | 1/4 (25.0%) |
| Exact-name homonyms | 2/3 (66.7%) | 1/3 (33.3%) | 0/3 (0.0%) | 2/3 (66.7%) |

| Case | Kind | Outcome | Acceptable |
|---|---|---|---|
| `g01_radiohead` | exact_unique | auto_correct | yes |
| `g02_studio_ghibli` | exact_unique | auto_correct | yes |
| `g03_phoenix` | exact_homonym_intended_not_first | auto_wrong | **NO** |
| `g04_titanic` | exact_with_nonexact_distractor | auto_correct | yes |
| `g05_interpol` | exact_homonym_intended_not_first | auto_wrong | **NO** |
| `g06_pulp` | exact_with_nonexact_distractor | auto_correct | yes |
| `g07_prince` | exact_with_nonexact_distractor | auto_correct | yes |
| `g08_nirvana` | exact_homonym_intended_first | auto_correct | yes |
| `g09_ghibli_short` | no_exact_intended_present | abstain | yes |
| `g10_beatles_no_article` | no_exact_intended_present | abstain | yes |
| `g11_unresolvable` | unresolvable_expected | abstain | yes |
| `g12_case_normalization` | normalization | auto_correct | yes |
| `g13_phoenix_confirmed` | user_confirmed | confirmed_correct | yes |

- User-confirmed overlay bypasses search: **True**; resolves to the intended entity: **True** (n=1).
- Gold entity id/type/disambiguation survive adapter + `/api/entities/search` unchanged: **True**.
- `synthetic-arithmetic` — Recall@5 = 1.000, MRR = 0.833 over 12 author-written candidate lists. Recall@5/MRR over author-written candidate lists; verifies the metric maths only, not Qloo search quality (live, pending).

## 2. Constraints — `mocked-integration`

Only constraints production can enforce are scored. v1's violation rate used price and tag attributes the benchmark invented; v2 does not.

| Probe (through the real workflow) | Development | Held-out | All |
|---|---|---|---|
| Exact-name dislike excludes the venue | 15/15 (100.0%) | 32/32 (100.0%) | 47/47 (100.0%) |
| Case-variant exact-name dislike excludes it | 15/15 (100.0%) | 32/32 (100.0%) | 47/47 (100.0%) |
| Exclusion is disclosed to the user | 15/15 (100.0%) | 32/32 (100.0%) | 47/47 (100.0%) |
| All pooled venues disliked → empty, disclosed | 15/15 (100.0%) | 31/31 (100.0%) | 46/46 (100.0%) |
| Substring dislike excludes it (not supported) | 0/15 (0.0%) | 0/32 (0.0%) | 0/47 (0.0%) |
| Category dislike excludes it (not supported) | 0/15 (0.0%) | 0/32 (0.0%) | 0/47 (0.0%) |

- **Budget is not enforced** (`Candidate` has a price field: False). Disclosed as "not checked" when a budget is given: 4/4 (100.0%); spuriously disclosed when none is given: 0/44 (0.0%). No violation rate is computed.
- Constraints declared across the 48 scenario files: 26 ({'budget': 4, 'free_text_dislike': 14, 'venue_name_dislike': 0, 'free_text_exclusion': 8}); enforceable by production: **0**, unsupported: **26**.

## 3. Evidence faithfulness — `mocked-integration`

_Support is judged against the mock server's own served data; it shows the production mapping/labelling is faithful to its inputs, not real-world accuracy._

| Claim type | Supported by fixture |
|---|---|
| affinity | 140/140 (100.0%) |
| coverage_label | 221/221 (100.0%) |
| explanation_count | 140/140 (100.0%) |
| named_interest | 202/202 (100.0%) |
| **all displayed claims** | **703/703 (100.0%)** |

- Identifier leaks into user-visible text: **0**.
- Mapping completeness (fixture-credited interests that production displays): **202/331 (61.0%)** — see gap G1.
- Mock mode (`production-function`): all labelled synthetic = **True**, no Qloo-sourced interests = **True**, no affinity = **True**.

## 4. Ranking ablation (Experiment B) and end-to-end (Experiment A)

Pool = what the real workflow retrieved through the real adapter. 47 scenarios evaluated, 1 excluded (no retrievable pool (all interests unresolved or a fault)). Re-running the production ranker on the pool reproduces the workflow's own order in 47/47 (100.0%).

Fairness here is computed from each participant's own retrieval list, independent of every ranker's score. `rank_aggregation` optimises something close to *worst-member best rank*, so that column favours it by construction. These are structural measures, **not** quality.

**development**

| Ranker | Provenance | Mean coverage | All servable served | Served within own top-5 | Worst-member best rank (↓) | Top-3 Jaccard vs production |
|---|---|---|---|---|---|---|
| `popularity` | synthetic-arithmetic | 1.000 | 15/15 (100.0%) | 14/15 (93.3%) | 2.800 | 0.393 |
| `rank_aggregation` | synthetic-arithmetic | 1.000 | 15/15 (100.0%) | 15/15 (100.0%) | 1.000 | 0.593 |
| `affinity_only` | synthetic-arithmetic | 1.000 | 15/15 (100.0%) | 15/15 (100.0%) | 1.400 | 0.693 |
| `production` | production-function | 1.000 | 15/15 (100.0%) | 15/15 (100.0%) | 1.533 | 1.000 |
| `production_no_affinity` | production-function | 1.000 | 15/15 (100.0%) | 15/15 (100.0%) | 1.667 | 0.900 |

**held_out**

| Ranker | Provenance | Mean coverage | All servable served | Served within own top-5 | Worst-member best rank (↓) | Top-3 Jaccard vs production |
|---|---|---|---|---|---|---|
| `popularity` | synthetic-arithmetic | 0.956 | 28/32 (87.5%) | 28/32 (87.5%) | 2.179 | 0.431 |
| `rank_aggregation` | synthetic-arithmetic | 0.992 | 31/32 (96.9%) | 31/32 (96.9%) | 1.097 | 0.697 |
| `affinity_only` | synthetic-arithmetic | 0.982 | 30/32 (93.8%) | 30/32 (93.8%) | 1.500 | 0.691 |
| `production` | production-function | 0.984 | 31/32 (96.9%) | 31/32 (96.9%) | 1.548 | 1.000 |
| `production_no_affinity` | production-function | 0.984 | 31/32 (96.9%) | 31/32 (96.9%) | 1.613 | 0.953 |

**all**

| Ranker | Provenance | Mean coverage | All servable served | Served within own top-5 | Worst-member best rank (↓) | Top-3 Jaccard vs production |
|---|---|---|---|---|---|---|
| `popularity` | synthetic-arithmetic | 0.970 | 43/47 (91.5%) | 42/47 (89.4%) | 2.395 | 0.419 |
| `rank_aggregation` | synthetic-arithmetic | 0.995 | 46/47 (97.9%) | 46/47 (97.9%) | 1.065 | 0.664 |
| `affinity_only` | synthetic-arithmetic | 0.988 | 45/47 (95.7%) | 45/47 (95.7%) | 1.467 | 0.691 |
| `production` | production-function | 0.989 | 46/47 (97.9%) | 46/47 (97.9%) | 1.543 | 1.000 |
| `production_no_affinity` | production-function | 0.989 | 46/47 (97.9%) | 46/47 (97.9%) | 1.630 | 0.936 |

**Experiment A (all)** — process metrics only

| Method | Executed | Mean coverage | All servable served | Worst-member best rank (↓) |
|---|---|---|---|---|
| `full_common_thread` | yes | 0.989 | 46/47 (97.9%) | 1.630 |
| `popularity_baseline` | yes | 0.970 | 43/47 (91.5%) | 2.395 |
| `llm_only` | **PENDING** | n/a | n/a | n/a |

> The LLM-only baseline is **pending**: the adapter exists but no provider is configured and none was added. Whether any method yields recommendations people prefer is the human study's question.

## 5. Fault resilience — `mocked-integration`, end to end

end-to-end: mock HTTP -> QlooClient -> workflow -> FastAPI route. Expectations come from `docs/API_CONTRACTS.md`. **35/35** rows meet the contract; raw-body/secret/stack-trace leaks: **0**.

| Route | Stage | Fault | Call | Expected | Observed | Code | Requests |
|---|---|---|---|---|---|---|---|
| recommendations | search | http_400 | all | 503 | 503 | QLOO_BAD_REQUEST | 3 |
| recommendations | search | http_401 | all | 503 | 503 | QLOO_AUTH_ERROR | 1 |
| recommendations | search | http_403 | all | 503 | 503 | QLOO_AUTH_ERROR | 1 |
| recommendations | search | http_429 | all | 503 | 503 | QLOO_RATE_LIMIT | 1 |
| recommendations | search | http_500 | all | 503 | 503 | QLOO_UPSTREAM_ERROR | 3 |
| recommendations | search | timeout | all | 503 | 503 | QLOO_TIMEOUT | 3 |
| recommendations | search | connect_error | all | 503 | 503 | QLOO_NETWORK_ERROR | 3 |
| recommendations | search | invalid_json | all | 503 | 503 | QLOO_INVALID_JSON | 3 |
| recommendations | search | not_object | all | 503 | 503 | QLOO_BAD_RESPONSE | 3 |
| recommendations | search | empty | all | 200_failed | 200_failed | - | 3 |
| recommendations | search | malformed_items | all | 200_failed | 200_failed | - | 3 |
| recommendations | search | missing_results_key | all | 200_failed | 200_failed | - | 3 |
| recommendations | insights | http_400 | all | 503 | 503 | QLOO_BAD_REQUEST | 4 |
| recommendations | insights | http_401 | all | 503 | 503 | QLOO_AUTH_ERROR | 4 |
| recommendations | insights | http_403 | all | 503 | 503 | QLOO_AUTH_ERROR | 4 |
| recommendations | insights | http_429 | all | 503 | 503 | QLOO_RATE_LIMIT | 4 |
| recommendations | insights | http_500 | all | 503 | 503 | QLOO_UPSTREAM_ERROR | 4 |
| recommendations | insights | timeout | all | 503 | 503 | QLOO_TIMEOUT | 4 |
| recommendations | insights | connect_error | all | 503 | 503 | QLOO_NETWORK_ERROR | 4 |
| recommendations | insights | invalid_json | all | 503 | 503 | QLOO_INVALID_JSON | 4 |
| recommendations | insights | not_object | all | 503 | 503 | QLOO_BAD_RESPONSE | 4 |
| recommendations | insights | empty | all | 200_failed | 200_failed | - | 6 |
| recommendations | insights | malformed_items | all | 200_failed | 200_failed | - | 6 |
| recommendations | insights | missing_results_key | all | 200_failed | 200_failed | - | 6 |
| recommendations | insights | http_500 | 2 | 200_partial | 200_partial | - | 5 |
| recommendations | insights | timeout | 3 | 200_partial | 200_partial | - | 6 |
| recommendations | search | timeout | all | 200_partial | 200_partial | - | 6 |
| recommendations | search | http_429 | 1 | 503 | 503 | QLOO_RATE_LIMIT | 1 |
| recommendations | search | malformed_items | all | 200_partial | 200_partial | - | 6 |
| entities | search | http_429 | all | 503 | 503 | QLOO_RATE_LIMIT | 1 |
| entities | search | http_500 | all | 503 | 503 | QLOO_UPSTREAM_ERROR | 1 |
| entities | search | timeout | all | 503 | 503 | QLOO_TIMEOUT | 1 |
| entities | search | http_401 | all | 502 | 502 | QLOO_AUTH_ERROR | 1 |
| entities | search | invalid_json | all | 502 | 502 | QLOO_INVALID_JSON | 1 |
| entities | search | empty | all | 200_empty | 200_empty | - | 1 |

- **end to end in this benchmark** — HTTP status/exception/body faults at /search and /v2/insights, through the stateless route and /entities/search
- **unit level only in production tests** — adapter status-code and invalid-JSON mapping (tests/test_qloo_adapter.py); route and plan-route fault handling with injected QlooProviderError (tests/test_plans.py)
- **not tested offline anywhere** — real timeout durations, DNS/TLS failure, connection-pool exhaustion, retry/backoff (none implemented), response-size limits, real Qloo error-body shapes

## 6. Live Qloo — `live-request`

**Requests made in v2: 0.** none. The 43-request v1 spike ran against the stale 2b3f56c adapter and is historical, not evidence about the checkpoint.

Budget a subsequent, separately authorised validation would need (**upper bound 55**):

| Phase | Requests |
|---|---|
| L0 reachability probe of the checkpoint adapter | 1 |
| L1 entity-resolution gold: one /search per distinct gold query, to replace synthetic ids with reviewed real ids and measure real Recall@5/MRR | 11 |
| L2 six representative scenarios through the checkpoint workflow | 43 |

Insights calls per run are capped at 5 by Settings.qloo_max_insights_calls; no retries exist in the adapter, so a failed call is not repeated.

## 7. Human evaluation — `human-study`

**Status: PENDING.** Protocol and scripts are retained (bench/human_eval.py). No participant data exists and none was fabricated.

