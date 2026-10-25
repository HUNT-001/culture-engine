> # ⚠ HISTORICAL — NOT EVIDENCE ABOUT THE CHECKPOINTED PRODUCT
>
> This document is **CommonThreadBench v1**, written against the **stale base commit `2b3f56c`**
> (a scaffold with no plan-lifecycle routes, first-match entity resolution and 6 backend tests).
> The reviewed application checkpoint is **`746ee95`**. A read-only audit found that v1 measured
> the wrong software and, for several headline numbers, mostly measured its own synthetic
> fixtures. **Do not cite any figure below as a property of the current application.**
> The 9.3%, 55.6%, 50% and 100% figures are withdrawn; see the claim register in
> [`../COMMON_THREAD_BENCHMARK.md`](../COMMON_THREAD_BENCHMARK.md) §9 for what replaced them.
> It is kept unmodified below only so the withdrawn claims remain auditable.

---

# CommonThreadBench v1 — Methodology, Metrics & Limitations

**Status:** baseline evaluation harness (v1). This document defines *how* Common
Thread is measured. The *numbers* live in the machine-generated, reproducible
report [`COMMON_THREAD_BENCHMARK_RESULTS_V1_HISTORICAL.md`](COMMON_THREAD_BENCHMARK_RESULTS_V1_HISTORICAL.md)
(regenerate with `python -m bench.run_benchmark`).

> **Purpose.** Establish a reproducible baseline *before* any recommendation-quality
> changes, with evidence of correctness and comparative value — not merely more
> passing unit tests. This task **does not change** production ranking weights,
> entity-resolution logic, UI behaviour or architecture. The benchmark only
> observes the existing system through its public interfaces.

---

## 0. What the system actually is (verified at baseline)

Before measuring, we verified the current implementation against the product
brief. The repository is a **working scaffold**, and three capabilities the task
framing implies are **not yet implemented** (confirmed in code, consistent with
`README.md` §Status and the research brief §12):

| Capability | Brief requirement | Current code | Evidence |
|---|---|---|---|
| Entity resolution | Surface ambiguous matches for **user confirmation** | Silently takes `matches[0]`; no confirmation path | `app/workflows/nodes.py:50-58` |
| Hard constraints | Enforce `budget_per_person` and dislikes/exclusions | Collected in schema; **never read** by retrieval/ranking | `budget`/`dislikes` unused outside `schemas.py` |
| Group-plan collaboration | Plan create/join/preferences routes | Only the direct `POST /api/recommendations` exists | `app/api/routes/` |

These are **measured as gaps**, not fixed here (scope: baseline only). The
"latest interest-resolution implementation" present at the checkpoint is the
first-match policy above; no user changes were overwritten.

**Baseline test results (before benchmark code was added):**

- `python -m pytest` → **6 passed**.
- `python -m ruff check .` → **67 pre-existing errors** (not introduced by this
  work; mostly `E501` line length in `app/` and existing `tests/`).
- Frontend: no test script defined; `npm run build` (tsc + vite) → **builds OK**.
- Branch `feature/common-thread-bench` created from the verified checkpoint
  (HEAD `2b3f56c` on `claude/epic-mccarthy-mzmq7o`), not pushed.

---

## 1. Design principles

1. **Separate automated correctness from subjective quality.** Layer A and the
   quantitative dimensions test *invariants and process*; recommendation
   *quality* is only decided by Layer C human evaluation.
2. **A different venue list is not evidence of higher quality.** End-to-end
   comparisons report process metrics (coverage, fairness, constraint adherence,
   diversity); they never infer that method X is "better" from the fact that it
   returned different venues.
3. **Missing is not zero.** Where a participant did not rank / match a candidate,
   that candidate is excluded from that participant's mean, not scored 0 — except
   inside the unchanged production ranker, whose 0-imputation we *measure* and
   report rather than alter.
4. **No fabrication.** Unavailable baselines and un-collected human ratings are
   reported as *pending*, never invented.
5. **Offline-first and cost-bounded.** All automated tests and the offline
   benchmark run with synthetic fixtures and make **no** network calls. Live Qloo
   traffic is a small, documented, opt-in spike.
6. **Dev/held-out discipline.** A 16/32 split exists so behaviour can be inspected
   on dev without reporting-set contamination. **No production weights are tuned
   on the held-out set** (none are tuned at all in v1).

---

## 2. Three evaluation layers

### Layer A — Adversarial correctness (`tests/test_bench_adversarial.py`)

Deterministic behavioural-invariant tests driven by the real workflow +
ranking + provenance code, using the synthetic `ScriptedQlooProvider`. Coverage:

- Participant-order and interest-order invariance (holding retrieval fixed).
- Duplicate-interest idempotence; resistance to interest-count inflation by
  duplication.
- Extreme single-participant affinity vs group coverage.
- Missing / malformed / tied / non-comparable scores (no crash, deterministic
  tie-breaking).
- Ambiguous and incorrect entity matches, unresolved interests.
- Hard constraints, dislikes, empty feasible candidate sets.
- Invalid API responses, timeouts, rate limits, auth errors, partial results.
- Explanation-to-interest mapping (faithfulness), unknown entity IDs.
- Mock vs live labelling.

Requirements the current scaffold does **not** meet (hard-constraint
enforcement, ambiguity confirmation, dislike exclusion, empty-feasible handling)
are encoded as **`xfail(strict=True)`** so the gap is **visible and tracked** —
never silently green. If the system is later fixed, the strict-xfail converts the
unexpected pass into a failure, forcing the expectation to be updated. No
hard-constraint violation and no unsupported named-interest explanation passes
silently in the suite.

### Layer B — Controlled comparative benchmark

A fixed dataset of **48 scenarios** across **8 categories** (6 each), groups of
2–4 people, with a documented **16 dev / 32 held-out** split balanced across
categories (2 dev + 4 held per category). See §3.

- **Experiment A — end-to-end value** (`bench/e2e.py`): `full_common_thread`
  (real workflow), `popularity_baseline` (same universe ranked by popularity,
  **enforcing** the declared hard constraints), and `llm_only` (generic LLM, same
  inputs/constraints, **no** Qloo — a real adapter, reported *pending* unless a
  provider is configured). Process metrics only.
- **Experiment B — ranking ablation** (`bench/ablation.py`, `bench/rankers.py`):
  `popularity`, `rank_aggregation`, `affinity_only`, `full_common_thread`. **Every
  ranker receives the identical per-scenario candidate pool.** Missing-result
  handling is explicit (§4).

### Layer C — Human evaluation protocol (`bench/human_eval.py`)

A blinded, randomized procedure for **8–12 real groups** comparing the same three
end-to-end methods with consistent presentation. Implemented as scripts
(`template`, `assignment`, `report`); **no participant data is fabricated** and
incomplete ratings are skipped (listed), never imputed. Metrics defined in §5.3.
Results are **pending** until real people perform the evaluation.

---

## 3. Scenario dataset & split

- File: `backend/bench/data/scenarios.json` (machine-readable); regenerate with
  `python -m bench.dataset_builder` (idempotent; verify with `--check`).
- 48 scenarios, 8 categories × 6: `shared_tastes`, `conflicting_tastes`,
  `dominant_member`, `niche_vs_mainstream`, `cross_domain_bridge`,
  `ambiguous_resolution`, `constraints`, `sparse_and_failures`.
- Each scenario carries: inputs (location, budget, participants with
  interests/dislikes), constraints, `expected_properties` (behavioural
  correctness properties — never a gold "best venue" for a subjective task),
  plus fault/ambiguity/unresolvable annotations where relevant.
- Split: `backend/bench/data/split.json` — `development` (16), `held_out` (32).
- Entity-resolution gold: `backend/bench/data/entity_resolution_gold.json` —
  **manually verified** gold labels per ambiguous query. These ranked candidate
  lists are synthetic, human-authored illustrations (NOT live Qloo payloads);
  real Recall@5/MRR require the live spike (§7) and are **pending**.

All scenario data is synthetic. No live Qloo response bodies, credentials or
private data are embedded (asserted by `tests/test_bench_scenarios.py`).

### Synthetic candidate universes

For offline runs, each scenario gets a deterministic (seeded) **candidate
universe** (`bench/synthetic.py`): candidates with popularity, a per-person
price level and tags, plus a mapping from each resolved interest term to a ranked
candidate list whose overlap is category-controlled. This single universe is the
shared pool used by both the workflow-driving `ScriptedQlooProvider` and the
Experiment B rankers. **These are controlled structural probes, not a claim about
real taste correlations.**

---

## 4. Explicit missing-result handling (Experiment B)

Every ranker consumes the same `CandidatePool`.

| Ranker | Uses participant data? | Missing participant for a candidate |
|---|---|---|
| `popularity` | No (popularity only) | n/a |
| `rank_aggregation` | Mean reciprocal rank | **Excluded** from the mean (not 0) |
| `affinity_only` | Mean affinity, no fairness term | **Excluded** from the mean (not 0) |
| `full_common_thread` | Production group ranker (unchanged) | **Imputed as 0** in its average, plus a worst-member term |

The divergence in the last row is a property of the production ranker that we
**measure and report**, not a choice imposed by the benchmark.

---

## 5. Metric definitions (precise)

All metric functions are pure and unit-tested (`tests/test_bench_metrics.py`,
`tests/test_bench_human_eval.py`). Implementation: `bench/metrics.py`.

### 5.1 Entity resolution

- **Recall@5** — fraction of labelled queries whose human-verified gold entity
  appears in the resolver's top-5 candidates.
- **MRR** — mean of `1/rank` of the gold entity (0 if absent).
- **False automatic-confirmation rate** — models the current *take-first-match,
  no-confirmation* policy: fraction of queries where the rank-1 candidate ≠ gold.
  Reported overall and restricted to genuinely ambiguous queries (>1 candidate),
  where a wrong pick is *silent*.

### 5.2 Automated correctness / recommendation-process dimensions

- **Hard-constraint violation rate** — of displayed options with known
  attributes, the fraction whose candidate exceeds `budget_per_person` or carries
  an excluded tag. Options with unknown attributes are reported as `unknown`
  (never silently counted as passing).
- **Participant coverage** — participants represented in ≥1 option / total,
  computed from each option candidate's `participant_ranks` (**independent** of
  the model's `rank_score`/`group_coverage`).
- **Worst-member representation** — min over participants of the number of
  options representing them (the fairness floor).
- **Fairness gap** — max − min participant representation.
- **Option diversity** — distinct candidate entity_ids / number of options.
- **Explanation faithfulness** — fraction of option explanations that name **no**
  interest term absent from the resolved-evidence set (i.e. no fabricated
  per-person causal claim).
- **Venue validity** — offline, all candidates are synthetic (`demo`); live, the
  product emits Maps **search** links only and marks hours/identity unverified, so
  validity is reported as the fraction `verified` (0 by design) and the presence
  of a Maps link — not a claim of real current details.
- **Qloo request count / success-rate / latency** — recorded by
  `CountingQlooProvider`. Offline latency is local-call latency; real latency comes
  from the live spike.
- **Mock vs live execution status** — every result records its execution mode;
  mock/synthetic options are labelled "Synthetic demo data".

### 5.3 Human-evaluation metrics (Layer C)

Per method, across groups, from 1–5 member ratings:

- **Consensus@3** — fraction of groups with ≥1 of the top-3 options rated **≥4 by
  every member** and satisfying all hard constraints. A member who did not rate an
  option does not count as satisfying it.
- **Mean group satisfaction** — average individual mean relevance within a group,
  averaged across groups.
- **Worst-member satisfaction** — average across groups of each group's lowest
  individual mean relevance.
- **Disagreement gap** — within-group (max − min) individual mean relevance.
- **Novelty** and **willingness-to-try** — measured on separate 1–5 scales,
  independent of relevance.

---

## 6. Measured results (offline) — headline findings

Authoritative tables: [`COMMON_THREAD_BENCHMARK_RESULTS_V1_HISTORICAL.md`](COMMON_THREAD_BENCHMARK_RESULTS_V1_HISTORICAL.md).
Highlights at the current checkpoint:

- **Hard constraints are not enforced.** Overall displayed-option violation rate
  ≈ **9.3%** (dev 13.3%, held-out 7.1%), concentrated in the `constraints`
  category at ≈ **55.6%**. Five scenarios are flagged as measured gaps. In the
  empty-feasible-set case (`constraints_05`) the full system shows 3 options that
  all violate the exclusions, while the constraint-aware popularity baseline
  correctly returns **0** options.
- **Ambiguous entity resolution auto-confirms wrongly.** False
  automatic-confirmation rate = **37.5%** overall and **50%** on ambiguous queries
  (on the synthetic ER harness) — a direct consequence of the no-confirmation
  `matches[0]` policy.
- **Explanation faithfulness = 100%** across all 48 scenarios: no option
  explanation fabricates a per-interest causal claim, and no `cultural_bridge`
  label appears without genuine multi-profile coverage.
- **Graceful degradation:** all fault scenarios (timeout/rate-limit/invalid/auth)
  degrade to `partial`/`failed` with warnings and no unhandled exceptions; 5/6
  `sparse_and_failures` scenarios end `failed` with no options, as intended.
- **Ranking ablation (Experiment B):** on the shared pools, the production
  group-aware ranker has the **best worst-member representation** (≈2.21 vs
  affinity-only ≈1.85, popularity ≈1.81) and the **smallest fairness gap** (≈0.52
  vs affinity-only ≈0.79, popularity ≈0.90). Top-3 sets differ from the baselines
  (Jaccard ≈0.5–0.7), i.e. the group-fairness logic measurably changes and
  improves worst-member outcomes **on these synthetic structural probes** (not a
  real-world quality claim).
- **Experiment A (process only):** popularity baseline = 0% constraint violations
  (it enforces them); full system = 9.3% (the un-enforced-constraints gap). Which
  a group *prefers* is the Layer C question.

---

## 7. Live-Qloo observations (bounded spike)

Run with `python -m bench.run_live_qloo` (opt-in; see the script header). In this
environment the Qloo hackathon host is reached through a credential-injecting
proxy (`--force-proxy-auth`); **no key is read from or written to the repo**, and
**no response bodies, names or ids are stored** — only aggregate counts.

- **Reachability probe:** `/search?query=Radiohead&take=3` → reachable, 3
  candidates, 1 request, ~0.63 s.
- **Six representative live cases** (one per non-fault category):
  `shared_tastes_01`, `conflicting_tastes_01`, `dominant_member_01`,
  `niche_vs_mainstream_01`, `cross_domain_bridge_01`, `constraints_01`.
  - **All 6 completed** with 3 options and 0 unresolved interests.
  - **Total actual Qloo requests = 43, 0 failed** (per case: ~6–9 requests, split
    `/search` and `/v2/insights`), mean latency ~0.23–0.75 s/request.
  - This **validates the adapter contract** for these cases: the current `/search`
    and `/v2/insights` parameters work against the live hackathon host — a stronger
    result than the README's "unverified" caution, now verified for this subset.

**Live limitations (honest):** we deliberately do not store venue attributes, so
live hard-constraint-violation rate, live entity-resolution Recall@5/MRR and live
explanation faithfulness are **not** computed from the spike (they would need
labelled, retained data, which the hackathon terms and our privacy rule
discourage). These remain **pending** a dedicated, consented live-labelling pass.

---

## 8. Unavailable baseline & pending measurements

| Item | Status | Why |
|---|---|---|
| LLM-only baseline (Experiment A) | **PENDING** | No `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` configured. A real, runnable adapter with a fixed model/prompt/output-count is implemented (`bench/e2e.py::LLMOnlyBaseline`); it is not executed to avoid introducing a paid dependency. Configure a provider and re-run to populate the row. |
| Human evaluation (Layer C) | **PENDING** | Requires 8–12 real groups. Protocol + scripts implemented; no participant data collected or fabricated. |
| Live Recall@5 / MRR / constraint-violation / faithfulness | **PENDING** | Requires a consented, labelled live pass with retained attributes (beyond the aggregate-only spike). |

---

## 9. Reproduce the evaluation

From `backend/` (after `pip install -e ".[dev]"`):

```bash
# 1. Regenerate / verify the dataset (idempotent)
python -m bench.dataset_builder --check

# 2. Offline benchmark -> results JSON + rendered report (no network)
python -m bench.run_benchmark

# 3. Deterministic test suites (adversarial, metrics, scenarios, rankers, human-eval)
python -m pytest tests/test_bench_*.py -q

# 4. Human-evaluation protocol scaffolding
python -m bench.human_eval assignment --groups 10 --seed 1 --out assignment_key.json
python -m bench.human_eval template   --groups 10 --size 3 --out ratings_template.json
# ... collect real ratings into ratings.json, then:
python -m bench.human_eval report --ratings ratings.json --assignment assignment_key.json

# 5. Bounded live spike (opt-in; needs a live key or an injecting proxy)
MOCK_PROVIDERS=false QLOO_API_KEY=... python -m bench.run_live_qloo
```

Outputs: `backend/bench/results/benchmark_results.json`,
`docs/COMMON_THREAD_BENCHMARK_RESULTS.md`, and (git-ignored, local only)
`backend/bench/results/live/`.

---

## 10. Limitations

- Offline structural metrics use **synthetic** universes; they measure process
  and invariants, **not** real recommendation quality. Quality is Layer C's job.
- The synthetic universes encode category structure by design, so absolute
  offline coverage/fairness numbers reflect the fixtures, not real Qloo coverage.
  Comparisons *between methods on the same fixtures* are the meaningful signal.
- Entity-resolution metrics run on synthetic ranked lists to verify the harness;
  real values need the live labelling pass.
- The live spike is 6 cases through a proxy; it establishes reachability and
  adapter-contract validity, not statistical performance.
- The benchmark intentionally changes **no** production logic, so the gaps it
  surfaces (constraint enforcement, ambiguity confirmation, dislikes) are reported,
  not remediated.

---

## 11. Recommended next step (based on measured gaps)

The single highest-value, lowest-risk fix indicated by the measured results is
**hard-constraint enforcement** (budget + dislike/exclusion filtering) in
`validate_evidence`/ranking: the `constraints` category shows a ~55.6% displayed
violation rate and the empty-feasible case returns infeasible options, while a
trivial constraint-aware baseline already achieves 0%. Second is an
**entity-confirmation path** for ambiguous matches (false auto-confirmation ~50%
on ambiguous queries). Both should be made and then **re-measured on the held-out
set** using this harness (the `xfail` gap tests will flip to passing when fixed).
Live Recall@5/MRR and the human evaluation should be run before any
recommendation-quality tuning, so quality changes are judged against a real
baseline rather than venue-list differences.
