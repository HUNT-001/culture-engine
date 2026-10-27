# Common Thread

**Different tastes. One great plan.** Common Thread helps a small group (2–4 people) find places and experiences that fit everyone's *cultural* tastes, using [Qloo](https://docs.qloo.com/)'s cultural-affinity data. Each person says what they love (a band, a film, a cuisine…); the app finds venues in a chosen city that connect those tastes, and shows why.

Built for the Qloo hackathon. It runs end to end without any credentials in **demo mode** (synthetic data, clearly labelled) and against the live Qloo API in **live mode**.

## What it does

- **Collaborative group plans (multi-device).** One person creates a plan and shares a Plan ID plus a private share code. Others join from their own devices, add their own interests, and anyone with the share code can generate the group recommendation. Plans are anonymous (no accounts) and expire after 24 hours.
- **Quick Planner (same device).** A fallback that needs no shared plan and no database: enter everyone's interests on one screen and get a result immediately.
- **You confirm what each interest means.** Typing "Phoenix" could mean a city, a band or an actor. For every interest you search Qloo and pick the exact entity you mean. **Nothing is matched automatically** — no first-result and no exact-name guessing. An interest you have not confirmed is left out of the run, and the result says so (`status` is then `partial` or `failed`, never `complete`).
- **Affinity-aware group ranking.** Qloo returns venues for each person and for the whole group. A deterministic Python ranker (not an LLM) scores each venue per person from its result rank and Qloo's affinity score (normalised per person), then blends the group average, the least-served member's score and its rank in the combined-group query. Group coverage (how many people's own results include the venue) decides the labels: it offers up to three options — *Shared Ground*, *Cultural Bridge* and *Stretch Choice* — and falls back to a plainly-labelled *Alternative* when the evidence does not support the stronger label.
- **Traceable evidence.** Each recommendation shows the Qloo affinity signal and which of the group's interests Qloo linked it to (`matched_interests`, mapped only from Qloo's own explainability data), next to our own "group-fit" score and coverage, which are labelled as a heuristic and not a probability of enjoyment.
- **Honest live/mock labelling.** A pill in the header and a badge on every result say "Live Qloo" or "Demo / mock". Mock venues are fictional and labelled DEMO; live venues are labelled "not verified" because opening hours and availability are never claimed. Each result links to a Maps search.
- **Optional LLM wording.** An OpenAI-compatible endpoint can phrase the explanations. It cannot add venues or change the ranking. Without one, explanations are deterministic.

## How it works

```
React + Vite + TypeScript  ──HTTP──▶  FastAPI  ──▶  LangGraph workflow (one bounded graph)
                                        │            validate_request → resolve_entities → retrieve_insights
                                        │            → normalize_candidates → rank_options → validate_evidence
                                        │            → compose_response → validate_output
                                        ├──▶ Qloo adapter (QlooClient)      — only place that talks to Qloo
                                        └──▶ SQLAlchemy (SQLite locally, PostgreSQL in production) — plans only
```

`resolve_entities` binds only interests you confirmed. `retrieve_insights` then asks Qloo for venues per person plus one combined query, capped at `QLOO_MAX_INSIGHTS_CALLS` (default 5) Qloo Insights calls per run. A run never calls Qloo's search; search is used only by the interest picker (`GET /api/entities/search`). Qloo and LLM keys live only in the backend and are never sent to the browser.

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md), [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md).

## Run it locally

Prerequisites: Python 3.11+, Node.js 20+ (CI uses Node 22), Git.

**Backend (demo mode, no credentials):**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

`.env.example` defaults to `MOCK_PROVIDERS=true` and a local SQLite file. API docs: <http://localhost:8000/docs>.

**Frontend** (second terminal):

```bash
cd frontend
npm ci
cp .env.example .env.local       # Windows PowerShell: Copy-Item .env.example .env.local
npm run dev
```

Open the URL Vite prints (usually <http://localhost:5173>, which is the default allowed CORS origin).

## Configuration

Backend environment variables (names are those read in `backend/app/core/config.py`; see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_PROVIDERS` | `true` | `true` = synthetic demo data. `false` = live Qloo (requires `QLOO_API_KEY`; the app refuses to start its runtime without it). |
| `QLOO_API_KEY` | empty | Qloo hackathon API key. **Backend only; store as a host secret.** |
| `QLOO_BASE_URL`, `QLOO_SEARCH_PATH`, `QLOO_INSIGHTS_PATH` | `https://hackathon.api.qloo.com`, `/search`, `/v2/insights` | Qloo endpoints. |
| `QLOO_TIMEOUT_SECONDS`, `QLOO_MAX_INSIGHTS_CALLS` | `15`, `5` | Per-request timeout; Insights calls per run. |
| `DATABASE_URL` | `sqlite:///./common_thread.db` | Use PostgreSQL in production: `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` (psycopg 3). |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated exact frontend origins, no trailing slash or path. |
| `APP_ENV` | `development` | Reported by `/api/health`. |
| `PLAN_TTL_HOURS`, `MAX_PARTICIPANTS` | `24`, `4` | Plan lifetime and size. |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS` | empty / `15` | Optional OpenAI-compatible chat-completions explainer. All three of URL, key and model must be set to enable it. |

Frontend: `VITE_API_BASE_URL` is the backend URL **including `/api`** (default `http://localhost:8000/api`). It is baked in at build time. Only public values belong in `VITE_*` variables — never a Qloo or LLM key.

## Live mode

1. Set `QLOO_API_KEY` and `MOCK_PROVIDERS=false` in the backend environment (a host secret, or `backend/.env` locally; never commit `.env`).
2. Restart the backend and open `GET /api/health`: it must report `"demo_mode": false`. The app header then shows **Live Qloo**.
3. In the app, search for an interest and confirm an entity, then generate a group result. Each run uses one search per interest in the picker and up to 5 Insights calls, so watch your hackathon quota.

The adapter's request parameters and response parsing are isolated in `backend/app/providers/qloo.py`. An opt-in contract check, `backend/tests/test_qloo_live.py`, runs only when `QLOO_API_KEY` is exported in your shell (at most two requests). Do not commit real Qloo responses; the hackathon terms restrict redistributing them.

## Deployment

The backend and the frontend are deployed **separately**. `render.yaml` defines **only the backend** web service; the frontend is a static site on a separate host.

1. **PostgreSQL (required for real use).** Create a persistent PostgreSQL database. A free host's local disk is ephemeral, so the SQLite default would lose every plan on redeploy. Convert the provider's connection string to the psycopg 3 form `postgresql+psycopg://…` and keep it secret. Tables are created automatically on startup (there are no migrations yet), so use a fresh database; a database created by an older version may lack newer columns.
2. **Backend (Render).** Create a Blueprint from `render.yaml` (root `backend`, build `pip install -e ".[dev]"`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`). The file declares four dashboard-managed values (`sync: false`, so Render asks you for them and they are never stored in git):
   - `DATABASE_URL` — the PostgreSQL URL above.
   - `CORS_ORIGINS` — the exact frontend origin, e.g. `https://your-frontend.example.com`.
   - `MOCK_PROVIDERS` — `true` for a safe demo, `false` for live. If left unset the app defaults to mock.
   - `QLOO_API_KEY` — your Qloo key (only needed when `MOCK_PROVIDERS=false`).
3. **Frontend (static site, e.g. Cloudflare Pages or Render Static Site).** Root `frontend`, build `npm ci && npm run build`, publish directory `dist`, environment variable `VITE_API_BASE_URL=https://<backend-host>/api`. Rebuild whenever that value changes. The app has no client-side routes, so no rewrite rules are needed.
4. **Verify.** `GET https://<backend-host>/api/health` returns `status: ok` and the expected `demo_mode`. Create a plan on one device, join it from another, and run a recommendation. Check the cold start of a free-tier backend before a demo, since the first request after idle can be slow.

The deployed backend authenticates to Qloo with its own `QLOO_API_KEY`; nothing depends on any development-session proxy.

## Tests

```bash
# Backend (from backend/)
pytest                                    # unit, API, lifecycle and the offline benchmark suite
ruff check .                              # note: the repository has inherited lint findings

# Frontend (from frontend/)
npm test                                  # vitest
npm run build                             # type-check + production build

# Offline benchmark report (from backend/)
python -m bench.run_benchmark             # regenerates docs/COMMON_THREAD_BENCHMARK_RESULTS.md
```

The backend tests use synthetic fixtures and never contact Qloo; the benchmark blocks outbound sockets. The benchmark's baseline guard inspects git history, so run the tests from a full clone (CI uses `fetch-depth: 0`).

## Evidence and evaluation

CommonThreadBench (`backend/bench/`, [`docs/COMMON_THREAD_BENCHMARK.md`](docs/COMMON_THREAD_BENCHMARK.md)) is an **offline, synthetic** evaluation that drives the real adapter, workflow and routes against Qloo-shaped mock responses. Its numbers describe our code's behaviour on invented data, **not** the accuracy of Qloo or of real-world recommendations. In particular, "0 false automatic confirmations" is a consequence of the confirm-every-interest policy, not a measure of entity-resolution accuracy. A small, bounded live observation of Qloo's entity search was made during development (qualitative only, no accuracy figures), and the human evaluation of recommendation quality is **pending**. The earlier v1 benchmark figures were withdrawn and are kept only as history in [`docs/benchmark-history/`](docs/benchmark-history/).

## Known limitations

- **Budget is recorded but not enforced.** Qloo's place data used here carries no prices, so a budget cannot be checked; results say it was not checked.
- **Evidence shows only the first Qloo explanation per venue.** When several people's queries return the same venue, only the first returned explanation is kept, so some linked interests are not displayed.
- **Dislikes** exclude only venues whose name matches exactly (case-insensitive); broader dislikes ("loud bars") cannot be checked.
- **Every interest needs a search and a pick.** An interest with no Qloo candidate cannot be used. In a collaborative plan only each person can confirm their own interests; a run still proceeds without anyone's unconfirmed ones and says so.
- **Venue facts are not verified** (hours, availability, safety). Treat results as discovery signals and check before travelling.
- **Plans are anonymous and expire** after `PLAN_TTL_HOURS`; closing the browser tab ends the device's session, so keep the Plan ID and share code to rejoin.
- No migrations (schema is created at startup), no rate limiting, and free-tier hosting may sleep or have retention limits — review before any public launch.
- Rankings use provisional coefficients that have not been calibrated against real human preferences.

## Repository map

- `backend/app` — FastAPI app, LangGraph workflow, Qloo adapter, ranking, evidence, plan persistence.
- `backend/tests` — unit, API and lifecycle tests plus the benchmark tests; `backend/bench` — CommonThreadBench.
- `frontend/src` — React app (`components/`, pure logic and tests in `lib/`, API client in `api/`).
- `docs/` — architecture, workflow, API contracts, research notes and benchmark documents.
- `render.yaml` — backend service blueprint; `.github/workflows` — CI.
