# CommonThreadBench v2 — Methodology, Metrics, Gaps and Limits

**Status:** offline, production-linked evaluation of the reviewed application checkpoint
`746ee952f7569d630f0a4488e5f75e6ece432060`. Generated numbers live in
[`COMMON_THREAD_BENCHMARK_RESULTS.md`](COMMON_THREAD_BENCHMARK_RESULTS.md) (regenerate with
`python -m bench.run_benchmark`); the per-test production-function map is in
[`COMMON_THREAD_BENCHMARK_FUNCTION_MAP.md`](COMMON_THREAD_BENCHMARK_FUNCTION_MAP.md).

> **This slice evaluates; it does not improve.** No production ranking, resolution, frontend
> behaviour or configuration was changed. Gaps found are reported, not fixed.

---

## 1. What went wrong in v1, and the guard that stops it recurring

v1 was built on commit `2b3f56c` (a scaffold) while the reviewed checkpoint is `746ee95`
(seven commits later: plan lifecycle, Qloo response parsing, affinity-aware ranking,
user-confirmed resolution, evidence mapping, collaborative UI). The local clone had only
ever fetched `main`, so the checkpoint was absent and v1 silently measured the wrong
software. A read-only audit then showed v1's headline numbers were also insensitive to the
application: **the unmodified v1 benchmark produced identical figures on both versions.**

v2 fixes the cause and the symptom:

| Cause | v2 fix |
|---|---|
| Wrong base, unnoticed | `bench/baseline_guard.py` checks git ancestry of the required checkpoint, that 8 API paths are registered **on the live app's OpenAPI schema**, and that 8 production features exist. It runs in the CLI, in `build_results`, and in `tests/test_bench_baseline_guard.py`; a stale base fails loudly. |
| Metrics that measured fixtures | v1 invented price/tag attributes then "measured" violations; a standalone function modelled the old `matches[0]` policy on rigged lists; "faithfulness" checked a word list that production explanations could not fail. v2 drives the **real** adapter, workflow and routes and judges production output against independently recorded ground truth. |
| Insensitivity | Verified: run against the stale `2b3f56c` app, the guard refuses (6 of 8 routes absent) and, with it bypassed, resolution outcomes flip, exact-name dislikes stop working and the evidence fields vanish. |

## 2. Evidence provenance — every metric carries one tag

| Tag | Meaning |
|---|---|
| `synthetic-arithmetic` | benchmark-side arithmetic on synthetic inputs; verifies metric maths only |
| `production-function` | a real production function called directly with synthetic inputs |
| `mocked-integration` | the **real** `QlooClient`, workflow and API routes driven by Qloo-shaped fixtures over an in-process `httpx.MockTransport`. Real production code, **not** the real Qloo service. Never call this "live". |
| `live-request` | a request that reached the Qloo API — **none in v2** |
| `human-study` | ratings from real people — **none collected** |

## 3. How v2 exercises production code

```
scenario inputs ─▶ world (invented venues, interest entities, per-entity affinity scales,
                         ties, missing affinity, noisy explainability)
                       │
              QlooMock (httpx.MockTransport; Qloo-documented /search and /v2/insights shapes;
                       │  faults injected as HTTP status / transport exception / body)
                       ▼
   REAL QlooClient ─▶ REAL workflow (resolve → retrieve → merge/dislike/rank → select →
   (parsing, error      label → compose → validate) ─▶ REAL FastAPI routes
    mapping)                                              (/recommendations, /entities/search, /plans/*)
```

**Real:** URL/param construction, status→error mapping, JSON handling, entity parsing,
`_extract_explanation`, exact-match/confirmation resolution, request budget, dislike
filtering, per-participant affinity normalisation, ranking, option selection, evidence
mapping, composer, provenance labels, route status mapping.
**Synthetic:** the venues, interests, affinities and every response body. The wire is a
mock; no socket is ever opened (outbound sockets are blocked at the OS level in the CLI and in
every bench test that runs the pipeline; the three pure-data test files do not need it).

Not run live, so **nothing here shows the real Qloo service behaves like the fixtures.**

## 4. Dataset and gold

- **48 scenarios, 8 categories × 6, groups of 2–4; 16 development / 32 held-out** (2+4 per
  category). `scenarios.json` and `split.json` are **byte-identical to v1** (SHA-256 pinned in
  `tests/test_bench_scenarios.py`). Only the *inputs* are used; v1's `expected_properties`
  blocks were written against the stale baseline and are **ignored**.
- **Entity-resolution gold (`bench/gold.py`): 13 cases, rewritten.** Each case records the
  *intended* entity (id, type, disambiguation) independently of search order and name
  similarity; an outcome is "wrong" only if production picks a different entity, never
  because a name differs from the typed phrase. **Review status, stated plainly: synthetic
  placeholder ids, author-written types/disambiguation, not human-verified, not
  live-verified.** v1 labelled its gold `manual`; that overstated it. Real-id gold needs the
  live slice (§10).
- Standalone probe cases (no scenario) are classed `development`; the six scenario-linked
  cases inherit their scenario's split.

## 5. Metric definitions

**Entity resolution — `mocked-integration`** (`bench/eval_resolution.py`)
Each gold case runs through the real `resolve_entities` via the real adapter. Outcomes:
`auto_correct`, `auto_wrong`, `abstain` (left unresolved for the user), `confirmed_correct`,
`confirmed_wrong`.
- *False automatic-confirmation rate* = `auto_wrong` ÷ (unconfirmed phrases that have a
  verified intended entity). It is a rate over those phrases, not over all cases.
- *Auto-confirmation precision* = `auto_correct` ÷ (`auto_correct` + `auto_wrong`).
- *Abstain rate*; *confirmed-path correctness*; *unacceptable-outcome rate* (outcome outside
  the case's acceptable set; `auto_wrong` is never acceptable).
- Gold id/type/disambiguation fidelity through the adapter and `/api/entities/search`.
- Recall@5 / MRR over the gold candidate lists are `synthetic-arithmetic`: the lists are
  author-written, so they test the formula only, not Qloo's search.

**Constraints — `mocked-integration`** (`bench/eval_constraints.py`)
Only what production can enforce is scored: **exact-name dislikes** (case-insensitive,
trimmed; pooled across participants). For each scenario the top displayed venue is
disliked by name and the real workflow re-run.
- *Enforcement* = venue absent from both the ranked pool and the displayed options;
  *disclosure* = a "stated dislike" warning; *empty-feasible handling* = disliking every
  pooled venue yields zero options and a "No usable recommendations" warning.
- Substring and category dislikes are probed to **document** that they are not enforced.
- **Budget is an unimplemented capability** (`Candidate` has no price field; the workflow
  records the budget and warns it was "not checked"). No violation rate is computed for it,
  or for any unsupported constraint. The report gives disclosure rates and the share of
  scenario-declared constraints that are enforceable (0 of 26).

**Evidence faithfulness — `mocked-integration`** (`bench/eval_evidence.py`)
A *displayed claim* is a statement on an option card. Types: `named_interest`, `affinity`,
`coverage_label` (option type and "k/N" text), `explanation_count`. Support is judged
against what the mock **actually served** (independently recomputed from the request log,
never from the model's `group_coverage`/`rank_score`). Also: identifier leakage into any
user-visible text, and *mapping completeness* (fixture-credited interests ÷ displayed).
**Support against a fixture shows production is faithful to its inputs; it is not a claim
about real-world accuracy.** Unknown ids, malformed/absent explainability, malformed
affinity, case-variant ids and mock mode are exercised in `tests/test_bench_evidence.py`.

**Ranking and ablation — `production-function` / `synthetic-arithmetic`** (`bench/eval_ranking.py`)
The pool is whatever the real workflow retrieved through the real adapter. Every ranker
sees exactly that pool; re-running the production ranker on it reproduces the workflow's
own order in 47/47 scenarios.
- Standalone baselines (no production imports, asserted by test): `popularity`
  (fixture-side; `Candidate` drops Qloo's popularity), `rank_aggregation`, `affinity_only`.
- Production rows (real `merge_candidate_batches` → `apply_hard_constraints` →
  `rank_candidates`): `production`, and `production_no_affinity` (same pool, affinity
  removed, isolating that feature).
- Metrics, computed from each participant's own retrieval list and **independent of every
  ranker's score**: *coverage* (servable participants with ≥1 top-3 item in their own list),
  *all servable served*, *served within own top-5*, *worst-member best rank* (lower is
  better), *top-3 Jaccard vs production*. "Servable" excludes a participant with no
  resolved list, identically for every method.
- **Missing data:** baselines exclude absent participants from an item's mean; production
  imputes 0 and adds worst-member and combined-profile terms. Both are measured as-is.
- Experiment A compares what the product *displays* (`select_options`) with the popularity
  baseline; the LLM-only baseline is **pending** (adapter present, no provider configured,
  no call made).

**Fault resilience — `mocked-integration`** (`bench/eval_faults.py`)
35 rows: 9 provider failures and 3 benign-bad payloads at both stages, partial/nth/query-
scoped faults, fatal-code short-circuit, and `/entities/search`. Faults are HTTP statuses,
simulated transport exceptions and bodies, so the **adapter** maps them and the **route**
maps the result. Expectations come from `docs/API_CONTRACTS.md` (503 only when the provider
is unavailable *and* there is no valid partial result; 200 with warnings otherwise; never a
raw body, stack trace or secret). A simulated `ReadTimeout` exercises exception handling,
not timer behaviour.

**Request counts and latency.** Offline counts come from the mock transport's request log
and are `mocked-integration` only. **No latency is reported:** local mock latency would
mean nothing about Qloo.

## 6. Test-level coverage: end-to-end vs unit

| Level | Where |
|---|---|
| End to end (mock HTTP → adapter → workflow → route) | all 35 fault rows; entity resolution; constraints; evidence; plan-route fault with persistence check |
| Unit / function level | production's own `test_qloo_adapter.py` (status mapping), `test_affinity_ranking.py`, `test_evidence.py`; this suite's `test_bench_ranking.py` invariance tests |
| Injected-exception route tests (production's `test_plans.py`) | prove route mapping only; **not** HTTP→error mapping |
| Not tested offline anywhere | real timeout durations, DNS/TLS, connection-pool exhaustion, retry/backoff (none implemented), response-size limits, real Qloo error bodies |

The measured function-by-test table is in the function map document.

## 7. Headline results (see the results document for all tables)

| Finding | Value | Tag |
|---|---|---|
| False automatic confirmation (unconfirmed, intended entity known) | **2/11 (18.2%)**; both are exact-name homonyms | `mocked-integration`, n=13, synthetic gold |
| Exact-name dislike enforced / disclosed | **47/47** / **47/47** (+ case variants 47/47) | `mocked-integration` |
| Empty feasible set handled and disclosed | **46/46** | `mocked-integration` |
| Substring / category dislike enforced | **0/47** (unsupported by design) | `mocked-integration` |
| Scenario-declared constraints enforceable by production | **0 of 26** | dataset + `production-function` |
| Budget | **not enforced**; disclosure 4/4, no false disclosure 0/44 | `mocked-integration` |
| Displayed claims supported by fixture | **703/703**; identifier leaks 0 | `mocked-integration` |
| Mapping completeness (credited interests displayed) | **202/331 (61.0%)** | `mocked-integration` |
| Fault matrix meets documented contract | **35/35**; leaks 0 | `mocked-integration` |
| Ranking: all servable participants served (47 scenarios) | rank_aggregation 46, production 46, affinity_only 45, popularity 43 | `production-function` / `synthetic-arithmetic` |
| Ranking: mean worst-member best rank (↓ better) | rank_aggregation 1.07, affinity_only 1.47, production 1.54, popularity 2.40 | same |
| Affinity's effect on production's top 3 | Jaccard 0.94 vs the no-affinity run | `production-function` |
| Live requests / human participants | **0 / 0** | — |

`rank_aggregation` optimises something close to *worst-member best rank*, so that column
favours it by construction.

**What these do not show:** that any method yields recommendations people prefer, that the
fixtures resemble real Qloo data, or that the production ranker is "better" or "worse"
overall. They are structural process measures on invented venues.

## 8. Newly discovered gaps (verified against production behaviour; none fixed here)

| # | Gap | Evidence |
|---|---|---|
| G1 | **Only the first captured explanation per venue is used.** `merge_candidate_batches` keeps the first non-None `qloo_explanation`, so interests credited by other participants' queries for the same venue are not displayed (202 of 331 fixture-credited interests surfaced; displayed names equal the first served response in 140/140 options). Weakens the "why this works for each person" claim. | `test_all_fixture_credited_interests_are_displayed` (`xfail(strict)`), `test_displayed_interests_equal_the_first_served_explanation` |
| G2 | **Exact-name homonyms are silently auto-confirmed to the first match** (Phoenix city vs band; INTERPOL organisation vs band). The confirmation picker fixes it, but unconfirmed input does not ask. | `test_exact_name_homonym_is_not_silently_bound_to_the_wrong_entity` (`xfail(strict)`) |
| G3 | **Inconsistent status for non-retryable provider errors:** `/api/recommendations` returns 503, `/api/entities/search` returns 502 for the same `QLOO_AUTH_ERROR`. | `test_non_retryable_errors_are_503_on_recommendations_but_502_on_entity_search` |
| G4 | **Budget and category dislikes cannot be enforced:** no price or category data on `Candidate`. Disclosed correctly, but 0 of the 26 constraints declared across the 48 scenarios can be enforced. | `test_candidate_schema_has_no_price_or_budget_field` |
| G5 | **A down provider still costs one `/search` per distinct interest, and nothing is retried.** Non-fatal search failures are not short-circuited (fatal auth/rate-limit codes are; the Insights stage stops at its first failure). Cost/latency, not correctness. | `test_a_down_provider_still_costs_one_search_per_interest_and_never_retries` |
| G6 | **Fixture-over-HTTP output is indistinguishable from live output in the API** (`source:"qloo"`, `demo_mode:false`, "not independently verified"); only the harness can tell. Benchmark output must never be shown or persisted as product output. | `test_mocked_http_path_is_not_labelled_demo_even_though_it_is_fixture_data` |
| G7 | **`Candidate` discards Qloo's `popularity`,** so a popularity baseline cannot be run on live data without retaining it. An evaluation constraint, not a defect. | `bench/rankers.py` (fixture-side popularity) |

Design properties recorded (not defects): dislikes are pooled, so one member's veto removes
a venue for the whole group; ties break by name descending.

## 9. Register of v1 claims

| v1 claim | Status | Why / replacement |
|---|---|---|
| "Scaffold: no lifecycle routes, first-match resolution, 6 baseline tests" | **Wrong base** | Checkpoint: 8 routes registered, exact-match + confirmation, 78 passed + 1 skipped |
| Hard-constraint violations 9.3% overall, 55.6% constraints category | **Withdrawn** | Scored against price/tags the benchmark invented. Replaced by exact-name enforcement (47/47) and unsupported-constraint prevalence (0/26 enforceable) |
| False auto-confirmation 50% (ambiguous), 37.5% overall | **Withdrawn** | A standalone function on rigged lists modelling the stale `matches[0]` policy. Replaced by 2/11 under the checkpoint's real policy (n=13, synthetic gold) |
| Explanation faithfulness 100% | **Withdrawn (vacuous)** | The composer never names interests and the synthetic provider emitted no explainability. Replaced by claim support 703/703 **plus** completeness 61.0% |
| "Production ranker has the best worst-member representation and smallest fairness gap" | **Withdrawn** | Compared on invented rank-only pools. On real-adapter pools production is **not** best on worst-member best rank |
| Experiment A: popularity baseline 0% violations vs full 9.3% | **Withdrawn** | Same invented attributes |
| "43 live requests validate the adapter contract" | **Historical** | Ran the stale `2b3f56c` adapter, which lacked affinity/explainability parsing. Not evidence about the checkpoint |
| 67 baseline Ruff errors; "fault scenarios degrade gracefully (5/6)" | **Superseded** | Checkpoint baseline is 110 Ruff findings (inherited); 35-row HTTP-level fault matrix |

The v1 documents are preserved, bannered, in [`benchmark-history/`](benchmark-history/).

## 10. Live-request budget for a later slice (none used here)

Computed from the mocked runs' own request logs; an **upper bound** (against the real
service some phrases will not exact-match and will issue fewer Insights calls). Insights
calls per run are capped at 5; the adapter has no retries.

| Phase | Purpose | Requests |
|---|---|---|
| L0 | reachability probe of the checkpoint adapter | 1 |
| L1 | one `/search` per distinct gold query, to replace synthetic ids with reviewed real ids and measure real Recall@5/MRR | 11 |
| L2 | six representative scenarios through the checkpoint workflow | 43 (6+7+9+7+7+7) |
| **Total** | | **≤ 55** |

`bench/run_live_qloo.py` refuses to run without `--confirm-live` and aborts at a hard
request cap. It needs separate authorisation and was not run.

## 11. Human evaluation (retained, pending)

`bench/human_eval.py` (blinded, randomized, 8–12 real groups, three methods, relevance /
novelty / willingness-to-try on 1–5 scales; Consensus@3, group satisfaction, worst-member
satisfaction, disagreement gap) is unchanged. Blank templates report `PENDING`; incomplete
cells are skipped and listed, never imputed. **No participant data exists or was invented.**

## 12. Validity limits

- Venues, interests, affinities and bodies are synthetic; absolute numbers reflect the
  fixtures. Comparisons between methods on the *same* fixtures are the meaningful signal.
- Entity-resolution n=13 with synthetic ids: rates are indicative, not estimates.
- The held-out split is reporting-only and nothing was tuned, but all 48 scenarios were run
  while building the evaluators, so held-out cases were not blind to their author. Treat the
  split as bookkeeping, not a blind test.
- Fairness columns favour rankers whose objective matches them; none is a quality measure.
- Popularity comes from the fixture, which production cannot see (G7).
- `mocked-integration` cannot reveal how the real Qloo service behaves.

## 13. Reproduce

```bash
cd backend && pip install -e ".[dev]"
python -m pytest -q                              # full suite
python -m ruff check bench tests/test_bench_*.py # changed files; repo-wide baseline is inherited
python -m bench.dataset_builder --check          # dataset + gold are reproducible
python -m bench.run_benchmark                    # offline; writes results JSON + report
python -m bench.function_map                     # measured production-function map (~3 min)
cd ../frontend && npm ci && npm test && npm run build
```

## 14. File map (v1 → v2)

Reused unchanged: `data/scenarios.json`, `data/split.json`, `human_eval.py`, `scenarios.py`,
`dataset_builder.py` (scenario/split generation). Rewritten: `gold.py` (replaces v1 gold),
`metrics.py` (circular functions removed). Replaced: `synthetic.py`, `providers.py`,
`harness.py`, `e2e.py`, `ablation.py`, `rankers.py`, `report.py`, `render.py`,
`run_benchmark.py` → `world.py`, `qloo_shape.py`, `runner.py`, `eval_*.py`,
`llm_baseline.py`, `live_budget.py`, `baseline_guard.py`, `provenance.py`. New:
`function_map.py`, `testing.py`.
