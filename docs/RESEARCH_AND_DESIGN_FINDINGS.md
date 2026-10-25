# Research & Design Findings — Phase 0 Audit

**Author:** Claude Code (cloud session, read-only Phase 0)
**Date:** 2026-10-24
**Scope:** Read-only audit + design research. No application code, dependencies, schema, deployment config or GitHub state were changed. No live Qloo/LLM calls were made (no credentials configured in this session and no user authorisation to use them).

Evidence labels used below: **DOCUMENTED FACT** (official/public source), **REPO-VERIFIED FACT** (I inspected the code / ran the check this session), **HYPOTHESIS** (plausible, untested), **OPEN QUESTION** (must be settled with evidence, usually a live spike).

---

## 0. What I did and did NOT test

**Did (this session):**
- Read: `README.md`, all five requested docs, and source for config, schemas, all providers (`qloo.py`, `mock_qloo.py`, `composer.py`), workflow (`graph.py`, `nodes.py`), services (`ranking.py`, `provenance.py`, `runtime.py`), API routes, DB models/session, `main.py`, frontend `App.tsx` and `api/client.ts`, and the three tests.
- Ran `pip install -e ".[dev]"` then `pytest` in `backend/`: **6 passed in ~1s** (REPO-VERIFIED FACT).
- Ran frontend `npm install` + `npm run build` (`tsc -b && vite build`): **exit 0**, 1934 modules, ~234 kB JS (73.8 kB gzip) (REPO-VERIFIED FACT).
- `grep` for any DB session/read/write usage across `backend/app` (REPO-VERIFIED FACT, see §2).
- Web research to corroborate Qloo endpoints and competitor claims.

**Did NOT test (and why):**
- **Any live Qloo request.** No key configured; no authorisation to use one. All Qloo request/response claims are therefore DOCUMENTED or OPEN, never verified against the live API.
- **docs.qloo.com could not be reached from this environment** (`getaddrinfo ENOTFOUND docs.qloo.com` — the host does not resolve under this container's network policy). So I could **not** re-verify the official hackathon guide first-hand this session. Qloo facts below rest on (a) the brief's own citations dated 2026-10-24 and (b) corroborating third-party hackathon repositories found via web search. Treat them as "documented per brief, independently corroborated, but unverified in-session."
- Live deploy / cold-start behaviour on Render/Cloudflare/Supabase.
- End-to-end request against a running backend (I ran unit/integration tests, not a manual live `curl`).
- Hands-on competitor task tests (the brief's competitor template requires these; not done).

---

## 1. Repository audit — current real state

**REPO-VERIFIED FACTS:**

1. **Backend architecture matches the docs.** One bounded LangGraph `StateGraph` with a linear node chain `validate_request → resolve_entities → retrieve_insights → normalize_candidates → rank_options → validate_evidence → compose_response → validate_output` (`graph.py`). Qloo is isolated behind `QlooClient`; ranking is deterministic Python independent of the LLM; the composer is explanation-only with a deterministic fallback. The stated architecture is faithfully implemented, not just described.
2. **Mock mode works end-to-end**; both the workflow test and the API test exercise it and assert synthetic/demo labelling. Success in mock mode proves wiring, **not** live Qloo integration.
3. **The database layer is entirely inert.** `get_db()` is defined but imported by nothing; there are zero `.add`/`.commit`/session calls anywhere in `app/`. `Base.metadata.create_all` runs on startup, but no plan, participant, preference or run is ever written or read. **Postgres as "source of truth" and "expiring anonymous plans" are currently aspirational — not implemented.**
4. **Only two routes are wired:** `GET /api/health` and `POST /api/recommendations`. None of the plan/share-link lifecycle endpoints in `API_CONTRACTS`/brief §8 exist. The frontend submits the whole group in one request; there is **no share link, no join flow, no feedback, no idempotency**.
5. **Entity resolution silently takes the first `/search` match** (`nodes.py:51-52`) — no disambiguation UI, confirmed as a known limitation.
6. **Request budget caps only Insights calls, not `/search` calls.** `query_count`/`qloo_max_insights_calls` (default 5) bound Insights requests (N participants + 1 combined). But `resolve_entities` issues one `/search` per *unique* interest term, uncounted against any budget. Worst case (4 participants × 3 distinct interests) ≈ **up to 12 search + up to 5 insights ≈ 17 Qloo calls/run** (REPO-VERIFIED from code paths).
7. **Error handling is asymmetric.** A `QlooProviderError` during `retrieve_insights` is caught and degraded to a partial/warning result (good). But the same error during `resolve_entities` is re-raised and aborts the whole run into a 503 (`nodes.py:44-45`) — one flaky interest lookup kills an otherwise-answerable group. Minor but contradicts the "preserve partial results" principle.
8. **Ranking is sensibly conservative.** `rank_candidates` uses normalised ordinal rank (not raw cross-request scores — aligns with brief guardrail), blends avg (0.60) / min (0.20) / combined (0.20), and `select_options` downgrades Shared Ground / Cultural Bridge / Stretch Choice to "Alternative" when evidence is insufficient. Tests assert the bridge label is never applied without multi-profile coverage. Weights are explicitly provisional (uncalibrated).
9. **Provenance/disclosure is honest:** demo/unverified labels, "rank score is not a probability of enjoyment", "venue details not verified", Maps *search* links only. Good.
10. **Sync SQLAlchemy engine in an otherwise-async app** (`session.py` uses `create_engine`). Harmless while the DB is unused, but blocking if DB access is later added inside async routes — use an async engine or a threadpool when you wire persistence.

**Overall:** the scaffold is clean, truthful about its own limits, and the "hard" parts (bounded graph, deterministic ranking, evidence discipline) are already correct. The *missing* parts are the group/collaboration product and any proof that live Qloo works.

---

## 2. Qloo API verification

> **Caveat (OPEN):** I could not reach `docs.qloo.com` from this session. The items below are **DOCUMENTED per the brief (checked 2026-10-24)** and independently **corroborated by multiple third-party Qloo Agentic Hackathon repositories** found via web search (e.g. public entrants describing their own calls). They are **not** verified against a live key this session.

**DOCUMENTED / corroborated:**
- Host `https://hackathon.api.qloo.com`; key in `X-Api-Key` header; hackathon keys don't work on prod/staging hosts.
- Insights = `GET /v2/insights`; entity lookup = `/search`; tags = `/v2/tags`. `/recs`/`/recommendations` are legacy/unsupported.
- `filter.type` is required on Insights; valid params depend on entity type. Place queries need a location filter and use `filter.type=urn:entity:place`.
- Interest signals are supplied via `signal.interests.entities` (comma-joined entity IDs) — exactly what `qloo.py:93` sends.
- A 200 with an empty `entities` array can mean invalid params / missing coverage; unsupported params may be silently ignored. **An HTTP 200 does not prove useful results** — matches the mission brief's warning.
- Hackathon keys have rate/monthly quotas and are deactivated after judging; private caching is allowed but Qloo payloads must not be committed to a public repo.

**OPEN QUESTIONS (resolve only with a private live spike):**
- **Location parameter name/shape.** Code uses `filter.location.query=<free text>`. Corroborating sources suggest `signal.location` is *not* in the current param guide and that geography filters (locality/WKT point + radius, e.g. `filter.location` + `filter.location.radius`) are the documented path. **Verify `filter.location.query` is accepted for `urn:entity:place`, or switch to the documented locality/point+radius filter.** This is the single most likely live-integration breakage.
- **Entity-type URN spelling.** A corroborating entrant reports `urn:entity:videogame` works while `urn:entity:video_game` returns HTTP 400. The current code relies on search-returned `type` strings rather than hardcoding, which is safer — but any hardcoded URN (docs/tests) must use the exact accepted spelling.
- **Explainability.** Code sends `feature.explainability=true` and reads `explanation`/`explainability`/`features`. Whether this flag is honoured for a *place+interest-signal* query, and what field it populates, is unverified. The brief's Cultural Bridge label depends on cross-profile provenance that this field is supposed to supply — **if explainability is absent/sparse for this query shape, the "bridge" claim must fall back to coverage-only evidence** (the code already supports that downgrade).
- **Cross-request rank/score comparability** — assume NOT comparable until proven; current ordinal approach is the safe default.

**Response-parsing robustness (REPO-VERIFIED):** `_result_list` tolerates several wrapper shapes (`results`/`entities`/`items`, dict-or-list) and the field extraction tries multiple key names. This is defensive and good; it also means a wrong-but-200 response could parse to an empty candidate set silently — so the live spike must assert *candidate counts*, not just status codes.

---

## 3. Three retrieval approaches compared

Assumptions: N = 2–4 participants, ≤3 interests each; Insights cap = 5; `/search` cached per unique term.

| | A. LLM-only baseline | B. Combined Qloo query | C. Qloo combined + per-person |
|---|---|---|---|
| Qloo calls/run | 0 (search optional) | ~search(≤12) + **1** insights | ~search(≤12) + **N+1** insights (≤5) |
| What it proves | nothing about Qloo value | Qloo changes candidates | + per-person representation & fairness |
| Enables "Shared Ground / Cultural Bridge" | no (no per-person coverage) | weak (no per-person rank sets) | **yes** (coverage per participant) |
| Main failure modes | hallucinated venues; no provenance | one participant dominates "combined" taste; sparse coverage looks like group consensus | highest cost; budget exhaustion skips combined query; sparse per-person results |
| Fit to product thesis | this is the baseline to **beat** | insufficient on its own | **required** for the fairness/bridge story |

**Finding (HYPOTHESIS, matches current code):** The product's differentiator (per-person fairness, Shared Ground vs Cultural Bridge) is only expressible under **C**, which the code already implements (per-participant batches + 1 combined). B alone cannot distinguish "everyone likes it" from "the loudest profile likes it." **Keep C**, but (a) count/limit `/search` calls, (b) make the combined query non-skippable by budgeting for it first, (c) gracefully reduce to B when the budget is tight, labelling the degradation.

**How to prove Qloo adds value (go/no-go experiment, brief §10):** run A/B/C on the *same* 3 synthetic group profiles with identical hard constraints; measure per-participant coverage, worst-participant coverage, option diversity, and run a small blind preference test (A vs C). The decisive test: **at least one scenario where C's option set or evidence is materially different from A's.** If not, the Qloo thesis fails and scope must change before any UI polish.

---

## 4. Competitor / substitute scan

Treat all competitive *gaps* as HYPOTHESES until a hands-on comparable task is logged (brief §4 template). What I could verify this session:

- **Yelp (DOCUMENTED FACT, announced 2026-10-20):** "Check for Me" AI voice agent calls restaurants for wait times; Yelp Assistant gained OpenTable bookings, Waitlist access, reminders and weather-aware recommendations; rolling out over coming months, US, iOS-first. → Strong on *single-user* local dining + live operational data (wait times/booking) — the very "practical verification" Common Thread defers. **Hypothesis to test:** Yelp stays within dining and is single-user, not cross-domain group taste. Sources below.
- **Google Ask Maps (Gemini), Group Table, Quewi, Spotify Blend:** not re-verified hands-on this session; the brief's links stand as references. HYPOTHESES: Maps = conversational single-user place discovery; Group Table = group *dining* preference matcher; Quewi = group *movie/TV*; Blend = shared *music* playlist. None is documented to do **cross-domain cultural bridging into real-world group outings** — but this must be tested, not asserted, per the brief.

**Positioning finding (HYPOTHESIS):** the defensible wedge is *cross-domain* (music+film+games+brands → a place) **+ per-person fairness** **+ evidence transparency**, not "group voting" (exists) or "live wait times" (Yelp already leads). Lead the demo with a case where differing domains produce a non-obvious shared place that an LLM-only answer wouldn't justify.

---

## 5. Minimum reliable demo scope (recommended lock)

One narrow vertical slice, mock-mode-safe, with a *real* live-Qloo path proven on 1 city:
1. Create plan → share link → 2–4 participants join and enter 1–3 interests (wire the DB; it's currently unused).
2. Entity resolution **with a confirmation step** for ambiguous matches (kills the silent-first-match risk).
3. Approach **C** retrieval within a hard, fully-counted call budget (search + insights).
4. Deterministic ranking → 3 evidence-labelled options with honest downgrades + Maps search links.
5. Demo-vs-live mode banner, warnings, unresolved interests, caveats — all already present in the UI.
6. One documented city chosen *after* a coverage spike; A/B/C comparison artefact for the submission.

Explicitly out of scope for MVP: accounts, live hours/availability verification (Google Places billing), payments, vector DB/Redis/queues, multi-agent loops.

---

## 6. Evaluation plan (condensed from brief §10)

- Entity-resolution success & ambiguity rate; candidate count & duplicate rate after normalisation.
- Per-participant coverage **and worst-participant coverage** (fairness is the headline metric).
- Cross-profile provenance availability (does explainability actually support "bridge"?).
- Option diversity; hard-constraint violations (must be 0); unsupported-explanation count (must be 0).
- A-vs-C blind preference ratings; calls/run and time-to-result.
- **Gate:** ≥1 scenario where Qloo (C) demonstrably changes the options/evidence vs LLM-only (A).

---

## 7. Prioritised action list (blockers first)

**P0 — must hold before trusting live data (do first, needs the key, privately):**
1. **Live Qloo spike** (brief §5 "minimum spike"): verify `X-Api-Key` auth; one `/search`; one `/v2/insights` place query; **settle the `filter.location.query` vs locality/point+radius question**; check whether `feature.explainability` returns anything for this query shape; record counts/latency/failure classes in `docs/API_SPIKE_REPORT.md` (sanitised, no payloads). **S.** *Owner decision: authorise key use.*
2. **Pick the demo city by measured coverage**, not assumption. **S** (rides on #1).

**P1 — core product gap (the slice):**
3. Wire the **plan → share link → join → preferences** lifecycle to the (currently unused) DB; add expiry/TTL and a random-token-hash join. **L.**
4. Add **entity-confirmation UI** for ambiguous matches. **M.**
5. **Count `/search` calls against a budget** and guarantee the combined query (reorder/pre-reserve). **S.**

**P2 — reliability / honesty:**
6. Degrade `resolve_entities` search failures to warnings (don't 503 the whole run). **S.**
7. Add ranking tests for 2/3/4 people, no-overlap, duplicates, missing per-profile ranks, and a persistently underserved participant. **M.**
8. A/B/C comparison harness on 3 synthetic profiles → submission artefact. **M.**

**P3 — pre-launch:**
9. Alembic migrations (replace `create_all`); use an async DB engine/threadpool if DB touches async routes. **M.**
10. Rate-limit plan/recommendation creation; set CORS to the exact deployed origin; rotate the dev secret; confirm free-tier cold-start UX. **M.**
11. OSS licence visible, public repo, demo video, submission text; re-check Devpost deadline (listed **2026-10-30 23:45 EDT**) immediately before submitting. **S.**

---

## 8. Recommendation: **MODIFY → GO (conditional)**

The engineering foundation is sound and honest, mock mode is green, and the frontend builds. But **two things are currently unproven and gate everything**: (1) live Qloo integration has never run (and the location-parameter assumption is the likely break point), and (2) the collaborative *product* — share link, join, persistence — does not exist yet; the DB is inert. Neither is a redesign; both are known, bounded work.

**Proceed, conditional on the P0 live spike succeeding** (auth works, a place+interest query returns a non-empty, location-correct candidate set, and A/C differ on ≥1 scenario). If the spike shows Qloo can't return usable cross-domain place candidates for a chosen city, **stop and narrow scope** (e.g. single-domain, or a different "shared experience" output) before building UI — do not compensate with more agents or more APIs.

### Five main blockers
1. **Live Qloo integration unverified** — esp. the `filter.location.query` location parameter and whether explainability is populated for place+interest queries (P0 #1).
2. **No group/collaboration product** — share link, join, persistence are unimplemented; DB is inert (P1 #3).
3. **Qloo-adds-value is unproven** — no A/B/C artefact yet; this is the hackathon's core judging hypothesis (P2 #8 / §3).
4. **Silent entity resolution + unbudgeted `/search`** — accuracy and cost risk under live keys/quota (P1 #4, #5).
5. **Deploy/free-tier reliability untested** — cold starts, CORS, secrets, quotas on Render/Supabase/Cloudflare (P3 #10).

### Next decisions (for the user)
- **Authorise private use of the hackathon key** so the P0 spike can run? (Nothing live was attempted without it.)
- **Confirm the vertical-slice scope** in §5 and the branch-per-feature plan before any implementation.
- Which **demo city** candidates to coverage-test first?

---

## Sources (accessed 2026-10-24)

- Qloo Agentic Hackathon Developer Guide — https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide *(cited by brief; host did not resolve from this session — not re-verified here)*
- Qloo API docs — https://docs.qloo.com/ *(not reachable this session)*
- Qloo Agentic Hackathon rules / Devpost — https://qloo.devpost.com/rules and https://qloo.devpost.com/
- Qloo Insights terms & functionality — https://www.qloo.com/resources/insights-by-qloo-defining-essential-terms-and-functionality
- Third-party hackathon entrants corroborating endpoint usage (`/v2/insights`, `filter.type`, `signal.interests.entities`, `/search`, `X-Api-Key`, `urn:entity:videogame` vs `video_game` 400, geography filters): e.g. https://github.com/takuya-auto/common-ground , https://github.com/Sourendas/common-ground-qloo , https://github.com/Daniel221287/tastebridge-qloo
- Yelp Fall 2026 release (Check for Me / Yelp Assistant) — https://www.yelp-press.com/press-releases/press-release-details/2026/Yelp-Announces-More-Personalized--Yelp-Assistant-Agent-that-Checks-Restaurant-Wait-Times-and-AI-Tools-for-Service-Professionals/default.aspx (corroborated: https://www.destinationcrm.com/Articles/ReadArticle.aspx?ArticleID=177129 , https://www.techdogs.com/tech-news/td-newsdesk/yelp-brings-ai-restaurant-calls-opentable-bookings-smart-lead-reply-more )
- Google Ask Maps — https://blog.google/intl/en-in/products/explore-communicate/ask-anything-about-any-place-on-maps-with-gemini/ ; Group Table — https://www.grouptable.ai/ ; Quewi — https://quewi.app/ ; Spotify Blend — https://support.spotify.com/article/blend/ *(brief references; not hands-on tested this session)*
