<div align="center">

<img src="docs/assets/logo.svg" alt="Common Thread logo: three threads converging into one" width="88" height="88" />

# Common Thread

**Where different tastes meet.**

A Qloo-powered cultural-discovery app that turns a group's different tastes into places everyone can enjoy.

[![Backend tests](https://github.com/HUNT-001/culture-engine/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/HUNT-001/culture-engine/actions/workflows/backend-tests.yml)
[![Frontend build](https://github.com/HUNT-001/culture-engine/actions/workflows/frontend-build.yml/badge.svg)](https://github.com/HUNT-001/culture-engine/actions/workflows/frontend-build.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Node 20+](https://img.shields.io/badge/node-20%2B-339933?logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

<img src="docs/assets/common-thread-demo.gif" alt="Screen recording of Common Thread: the hero, choosing the Quick Planner, searching and explicitly confirming each interest, then the three recommended options" width="860" />

<sub>The real app running in demo mode: pick a planner, search each interest, explicitly confirm the entity you mean, then see where the group's tastes meet.</sub>

[Features](#features) · [How it works](#how-it-works) · [Components](#major-components) · [Run it](#run-it-locally) · [Configuration](#configuration) · [Deploy](#deployment) · [For developers](#for-developers)

</div>

---

## Features

- **Shared plans across devices.** One person creates a plan and shares a Plan ID plus a private share code. Friends join from their own devices, add what they love, and anyone with the share code can generate the group result. Plans are anonymous (no accounts) and expire after 24 hours.
- **Quick Planner.** Everyone on one screen, no shared plan and no database needed. Enter each person's interests and get a result immediately.
- **You confirm what each interest means.** "Phoenix" could be a city, a band or an actor. For every interest you search Qloo and pick the exact entity you mean. Nothing is matched automatically, and the original wording and the confirmed entity are kept exactly as chosen.
- **Group-aware ranking.** Qloo is asked about each person and about the whole group. A deterministic Python ranker, not an LLM, blends each person's result rank with Qloo's per-person affinity and offers up to three options: **Shared Ground** (everyone overlaps), **Cultural Bridge** (several connect) and **Stretch Choice** (a worthwhile wildcard).
- **Traceable evidence.** Each pick shows coverage, Qloo's affinity signal and group-fit as three separate numbers, plus the interests Qloo linked it to, only when Qloo supplied that data.
- **Honest live/demo labelling.** A pill in the header and a badge on every result say **Live Qloo** or **Demo**. Demo venues are fictional and labelled; live venues are labelled "not verified". Each result links to a Maps search.
- **Optional LLM wording.** An OpenAI-compatible endpoint can phrase the explanations. It cannot add venues or change the ranking; without one, explanations are deterministic.
- **Thoughtful UI.** Responsive down to 360px, keyboard-accessible with visible focus, skip link and labelled controls, and `prefers-reduced-motion` support.

> Results are discovery signals, not guarantees. Venue hours, prices and availability are never claimed; check before you travel.

---

## How it works

### Full-stack architecture

```mermaid
flowchart TB
  subgraph Client["Browser: React + Vite + TypeScript"]
    direction LR
    PL["Planners<br/>Quick (same device)<br/>Collaborative (shared plan)"]
    IP["InterestPicker<br/>search, explicit confirm"]
    RP["ResultsPanel<br/>coverage, affinity, evidence"]
    STORE[("Browser storage<br/>sessionStorage: plan credentials<br/>localStorage: last quick plan")]
    PL --> IP
    PL --> RP
    PL -.-> STORE
  end

  subgraph Server["Backend: FastAPI on Python 3.11+"]
    direction LR
    ROUTES["Routers<br/>/health, /entities/search<br/>/recommendations, /plans/*"]
    FLOW["LangGraph workflow<br/>8 bounded nodes"]
    SERV["Services<br/>resolution, ranking,<br/>evidence, provenance"]
    PROV["Providers<br/>Qloo adapter or demo mock,<br/>response composer"]
    REPO["Repository<br/>SQLAlchemy"]
    ROUTES --> FLOW
    FLOW --> SERV
    FLOW --> PROV
    ROUTES --> REPO
  end

  DB[("Database<br/>SQLite (dev) or PostgreSQL (prod)<br/>plans, participants, preferences, runs")]
  QLOO(["Qloo API<br/>/search and /v2/insights"])
  LLM(["Optional LLM<br/>OpenAI-compatible, wording only"])

  Client -- "HTTPS JSON, tokens in headers" --> Server
  REPO --> DB
  PROV -- "API key, server-side only" --> QLOO
  PROV -.-> LLM
```

The browser never holds a Qloo or LLM key and never calls a provider directly. The same-device Quick Planner uses the stateless `/api/recommendations` route and never touches the database.

### The agent workflow

One bounded [LangGraph](https://langchain-ai.github.io/langgraph/) graph, with no open-ended tool loop and no agent swarm. Each node has a single job, and the LLM, if configured, only touches wording.

```mermaid
flowchart TD
  START([Request: location, people, confirmed interests]) --> V["validate_request<br/>schema and size bounds"]
  V --> E["resolve_entities<br/>binds only entities the user confirmed"]
  E -. "unconfirmed interests" .-> NC[/"excluded and reported<br/>needs_confirmation"/]
  E --> I["retrieve_insights<br/>one query per person plus one combined<br/>capped by QLOO_MAX_INSIGHTS_CALLS"]
  I -. "provider error" .-> PART[/"warning, partial results kept"/]
  I --> N["normalize_candidates<br/>merge, apply dislikes, rank<br/>link Qloo signals to interests"]
  N --> O["rank_options<br/>Shared Ground, Cultural Bridge,<br/>Stretch Choice, or Alternative"]
  O --> VE["validate_evidence<br/>live or demo labels, coverage notes"]
  VE --> C["compose_response<br/>deterministic text, optional LLM wording"]
  C --> VO["validate_output<br/>schema check before returning"]
  VO --> END([Response: options, warnings, status])
```

### How a recommendation is scored

```mermaid
flowchart LR
  subgraph Person["For each person"]
    R["Result rank<br/>in their own Qloo results"]
    A["Qloo affinity<br/>normalised per person"]
    R --> PS["Person score<br/>50% rank + 50% affinity<br/>(rank alone if no affinity)"]
    A --> PS
  end
  PS --> AVG["Group average"]
  PS --> MIN["Least-served person"]
  CMB["Rank in the combined-group query"]
  AVG --> FIT["Group-fit<br/>60% average + 20% minimum<br/>+ 20% combined rank"]
  MIN --> FIT
  CMB --> FIT
  COV["Coverage: how many people's own results include the venue"]
  FIT --> OUT["Ordered candidates"]
  COV --> LABEL["Option label<br/>Shared Ground, Cultural Bridge, Stretch Choice"]
  OUT --> LABEL
```

Qloo's affinity and linked interests are Qloo's signals; coverage and group-fit are Common Thread's own calculation, and the UI keeps them visibly separate.

### A shared plan, end to end

```mermaid
sequenceDiagram
  autonumber
  actor Host
  actor Friend
  participant UI as React app
  participant API as FastAPI
  participant DB as Database
  participant Q as Qloo

  Host->>UI: Create plan (city, optional budget)
  UI->>API: POST /api/plans
  API->>DB: store plan and a SHA-256 hash of the share token
  API-->>UI: plan_id and share_token (returned once)
  Host-->>Friend: Plan ID and share code, over a private channel
  Friend->>UI: Join with Plan ID and share code
  UI->>API: POST /api/plans/{id}/participants (X-Share-Token)
  API-->>UI: participant_id and participant_token
  loop each person
    UI->>API: GET /api/entities/search?query=...
    API->>Q: /search
    Q-->>API: candidate entities
    API-->>UI: name, type and disambiguation
    Note over UI: the person explicitly confirms one entity
    UI->>API: PUT .../preferences (X-Participant-Token)
    API->>DB: save interests and confirmed entity ids
  end
  Host->>UI: Generate recommendations
  UI->>API: POST /api/plans/{id}/recommendations (X-Share-Token)
  API->>Q: /v2/insights per person plus combined
  API->>DB: save the run
  API-->>UI: options, warnings, needs_confirmation, status
```

Tokens travel only in headers, never in URLs; the server stores only their hashes.

---

## Major components

```mermaid
flowchart LR
  subgraph FE["frontend/"]
    direction TB
    FE1["components/<br/>Quick, Collaborative, InterestPicker,<br/>ResultsPanel, Stepper, ThreadArt"]
    FE2["lib/<br/>interests, results, plan, invite,<br/>session, storage, present"]
    FE3["api/client.ts, types.ts"]
    FE1 --> FE2
    FE2 --> FE3
  end
  subgraph BE["backend/app/"]
    direction TB
    BE1["api/routes/<br/>health, entities, recommendations, plans"]
    BE2["workflows/<br/>graph, nodes, state"]
    BE3["services/<br/>resolution, ranking, evidence,<br/>provenance, runtime"]
    BE4["providers/<br/>qloo, mock_qloo, composer, interfaces"]
    BE5["db/ and core/<br/>models, repository, session,<br/>config, security"]
    BE1 --> BE2
    BE2 --> BE3
    BE2 --> BE4
    BE1 --> BE5
  end
  subgraph QA["Quality and delivery"]
    direction TB
    QA1["backend/tests/<br/>unit, API, lifecycle"]
    QA2["backend/bench/<br/>CommonThreadBench"]
    QA3[".github/workflows/ and render.yaml<br/>CI and backend deploy"]
  end
  FE -- "HTTP /api" --> BE
  QA -. "verifies and ships" .-> BE
```

| Area | Where | What it does |
|---|---|---|
| **App shell** | `frontend/src/App.tsx` | Hero, live/demo pill (from `/api/health`), switch between Collaborative and Quick planning. |
| **Planners** | `components/CollaborativePlanner.tsx`, `QuickPlanner.tsx` | The two flows. They share one confirmation gate, so an interest can't be submitted until it is confirmed or removed. |
| **Interest picker** | `components/InterestPicker.tsx` | Search Qloo, inspect candidates (name, type, disambiguation), explicitly confirm one. |
| **Results** | `components/ResultsPanel.tsx` | Result cards with the three separate metrics, evidence and status banners. |
| **Frontend logic** | `frontend/src/lib/` | Pure, unit-tested helpers: interest rows and validation, result presentation, sessions, invites. |
| **API routes** | `backend/app/api/routes/` | `health`, `entities` (candidate search), `recommendations` (stateless), `plans` (lifecycle). |
| **Workflow** | `backend/app/workflows/` | The LangGraph graph, its node functions and typed state. |
| **Services** | `backend/app/services/` | Entity-resolution policy, ranking, evidence mapping, provenance labels and the runtime wiring (mock vs live). |
| **Providers** | `backend/app/providers/` | Qloo adapter (`httpx`), demo mock, response composer (deterministic or LLM), and the provider interfaces. |
| **Persistence** | `backend/app/db/` | SQLAlchemy models (`plans`, `participants`, `preferences`, `recommendation_runs`), repository and sessions. |
| **Config & security** | `backend/app/core/` | Environment-driven settings and token hashing. |
| **CommonThreadBench** | `backend/bench/` | An offline evaluation harness that drives the real code against Qloo-shaped mock responses. |

| Layer | Stack |
|---|---|
| Frontend | React, Vite, TypeScript, lucide-react icons, Vitest |
| Backend | FastAPI, Pydantic v2, LangGraph, SQLAlchemy 2, httpx |
| Data | SQLite (local), PostgreSQL via psycopg 3 (production) |
| Cultural data | [Qloo](https://docs.qloo.com/) hackathon API (`/search`, `/v2/insights`) |
| Tooling | pytest, Ruff, GitHub Actions, Render |

---

## Run it locally

**Prerequisites:** Python 3.11+, Node.js 20+ (CI uses 22), Git. No API keys are needed: the app starts in **demo mode** with synthetic data.

**1. Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API is now on <http://localhost:8000> (interactive docs at `/docs`, health at `/api/health`). `.env.example` defaults to `MOCK_PROVIDERS=true` and a local SQLite file.

**2. Frontend** (second terminal)

```bash
cd frontend
npm ci
cp .env.example .env.local       # Windows PowerShell: Copy-Item .env.example .env.local
npm run dev
```

Open <http://localhost:5173> (the default allowed CORS origin).

**A 60-second tour:** choose **Try the Quick Planner**, press **Search** on an interest, then **Confirm** the entity you mean. Confirm the rest, press **Find our shared next thing**, and read the three options. To try the multi-device flow, open the app in a second browser profile, create a plan in one, and join from the other with the Plan ID and share code.

<details>
<summary><strong>Troubleshooting</strong></summary>

| Symptom | Likely cause and fix |
|---|---|
| Header pill says **Backend offline** | The API isn't running, or `VITE_API_BASE_URL` points elsewhere. It must end in `/api` (default `http://localhost:8000/api`). |
| Browser console shows a CORS error | Add your frontend origin to `CORS_ORIGINS` (exact origin, no trailing slash). |
| `QLOO_API_KEY is required` on start in live mode | `MOCK_PROVIDERS=false` needs a key. Set it, or switch back to `true`. |
| `psycopg2` import error with PostgreSQL | Use the psycopg 3 URL form `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`. |
| A few benchmark tests fail with "checkpoint commit is not present" | Run from a full clone (`git fetch --unshallow`); the benchmark's baseline guard inspects git history. |

</details>

---

## Configuration

Backend environment variables (read in `backend/app/core/config.py`; template in `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_PROVIDERS` | `true` | `true` = synthetic demo data. `false` = live Qloo (requires `QLOO_API_KEY`). |
| `QLOO_API_KEY` | empty | Qloo hackathon API key. **Backend only; store it as a host secret.** |
| `QLOO_BASE_URL`, `QLOO_SEARCH_PATH`, `QLOO_INSIGHTS_PATH` | `https://hackathon.api.qloo.com`, `/search`, `/v2/insights` | Qloo endpoints. |
| `QLOO_TIMEOUT_SECONDS`, `QLOO_MAX_INSIGHTS_CALLS` | `15`, `5` | Request timeout; Insights calls per run. |
| `DATABASE_URL` | `sqlite:///./common_thread.db` | PostgreSQL in production: `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated exact frontend origins. |
| `APP_ENV` | `development` | Reported by `/api/health`. |
| `PLAN_TTL_HOURS`, `MAX_PARTICIPANTS` | `24`, `4` | Plan lifetime and size. |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS` | empty / `15` | Optional OpenAI-compatible explainer. URL, key and model must all be set to enable it. |

Frontend: `VITE_API_BASE_URL` is the backend URL **including `/api`** (default `http://localhost:8000/api`). It is baked in at build time, and only public values belong in `VITE_*` variables, never a Qloo or LLM key.

### Live Qloo mode

1. Set `QLOO_API_KEY` and `MOCK_PROVIDERS=false` in the backend environment (never commit `.env`).
2. Restart the backend and check `GET /api/health` returns `"demo_mode": false`. The header pill then reads **Live Qloo**.
3. Search for an interest, confirm an entity, and generate a result. Each run uses up to 5 Insights calls, plus one search per interest in the picker, so watch your quota.

Request parameters and response parsing live in `backend/app/providers/qloo.py`. An opt-in contract check, `backend/tests/test_qloo_live.py`, runs only when `QLOO_API_KEY` is exported in your shell (at most two requests). Don't commit real Qloo responses: the hackathon terms restrict redistributing them.

---

## API at a glance

| Method and path | Auth header | Purpose |
|---|---|---|
| `GET /api/health` | none | Status and `demo_mode`. |
| `GET /api/entities/search?query=&take=` | none | Candidate Qloo entities for the picker. |
| `POST /api/recommendations` | none | Stateless group result (Quick Planner). |
| `POST /api/plans` | none | Create a plan; returns `plan_id` and a one-time `share_token`. |
| `GET /api/plans/{id}` | `X-Share-Token` | Plan, roster and latest result. |
| `POST /api/plans/{id}/participants` | `X-Share-Token` | Join; returns a `participant_token`. |
| `PUT /api/plans/{id}/participants/{pid}/preferences` | `X-Participant-Token` | Save interests with confirmed entities. |
| `POST /api/plans/{id}/recommendations` | `X-Share-Token` | Generate and store the group result. |

Request and response shapes, status codes and the confirmation rule are in [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md).

---

## Testing

```bash
# Backend (from backend/)
pytest                          # unit, API, lifecycle and the offline benchmark suite
ruff check .

# Frontend (from frontend/)
npm test                        # Vitest
npm run build                   # type-check + production build

# Offline benchmark report (from backend/)
python -m bench.run_benchmark   # regenerates docs/COMMON_THREAD_BENCHMARK_RESULTS.md
```

Tests use synthetic fixtures and never contact Qloo; the benchmark blocks outbound sockets. GitHub Actions runs the backend tests and the frontend build on every push (the backend job checks out full history, which the benchmark's baseline guard needs).

---

## Deployment

The backend and frontend deploy **separately**. `render.yaml` defines only the backend; the frontend is a static site.

1. **PostgreSQL.** Create a persistent database and convert its connection string to the psycopg 3 form `postgresql+psycopg://…`. Tables are created automatically on startup, so use a fresh database.
2. **Backend (Render).** Create a Blueprint from `render.yaml` (root `backend`, build `pip install -e ".[dev]"`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`). Render prompts for the four dashboard-managed values, which are never stored in git:
   - `DATABASE_URL`: the PostgreSQL URL above.
   - `CORS_ORIGINS`: the exact frontend origin, e.g. `https://your-frontend.example.com`.
   - `MOCK_PROVIDERS`: `true` for a safe demo, `false` for live (unset defaults to mock).
   - `QLOO_API_KEY`: your Qloo key (needed only when `MOCK_PROVIDERS=false`).
3. **Frontend (static site).** Cloudflare Pages or a Render Static Site: root `frontend`, build `npm ci && npm run build`, publish `dist`, and set `VITE_API_BASE_URL=https://<backend-host>/api`. Rebuild whenever that value changes. The app has no client-side routes, so no rewrite rules are needed.
4. **Verify.** `GET https://<backend-host>/api/health` returns `status: ok` and the expected `demo_mode`. Create a plan on one device, join from another, and run a recommendation. On a free tier the first request after idle can be slow.

The deployed backend authenticates to Qloo with its own `QLOO_API_KEY`; nothing depends on a development-session proxy.

---

## For developers

### Where to change what

| I want to… | Start here |
|---|---|
| Swap or add a data source | Implement the `QlooProvider` protocol in `backend/app/providers/interfaces.py`, then wire it in `services/runtime.py`. |
| Change how results are ranked | `backend/app/services/ranking.py`. Re-run `pytest` and `python -m bench.run_benchmark`. |
| Add or reorder a workflow step | `backend/app/workflows/nodes.py`, then register it in `graph.py`. |
| Add an API field | `backend/app/domain/schemas.py`, then `docs/API_CONTRACTS.md` and `frontend/src/types.ts`. |
| Add a setting | `backend/app/core/config.py`, `backend/.env.example` and the table above. |
| Restyle the UI | Design tokens live in `:root` at the top of `frontend/src/style.css`. |

### Design principles

- **Server-side keys.** Qloo and LLM credentials never reach the browser.
- **Explicit confirmation.** The server binds an interest to a Qloo entity only when the user chose it.
- **Deterministic ranking.** Ordering and labels come from tested Python, never from an LLM.
- **Bounded workflow.** One fixed graph with capped provider calls.
- **Honest labelling.** Demo vs live, and Qloo's signals vs our own calculations, are always distinguishable.

### Developer artifacts

| Artifact | What it is |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System boundary, core modules and trust boundaries. |
| [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md) | Workflow nodes, state rules and the LLM policy. |
| [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) | Endpoint contracts and error policy. |
| [`docs/COMMON_THREAD_BENCHMARK.md`](docs/COMMON_THREAD_BENCHMARK.md) | CommonThreadBench methodology, metrics and evidence tags. |
| [`docs/COMMON_THREAD_BENCHMARK_RESULTS.md`](docs/COMMON_THREAD_BENCHMARK_RESULTS.md) | Generated results (`python -m bench.run_benchmark`). |
| [`docs/COMMON_THREAD_BENCHMARK_FUNCTION_MAP.md`](docs/COMMON_THREAD_BENCHMARK_FUNCTION_MAP.md) | Which production functions each benchmark test exercises. |
| [`docs/RESEARCH_AND_DESIGN_FINDINGS.md`](docs/RESEARCH_AND_DESIGN_FINDINGS.md) | Research notes behind the design decisions. |
| [`docs/design-history/`](docs/design-history/) | The original product brief, early architecture sketches and first build plan (historical). |
| [`docs/assets/`](docs/assets/) | Logo and the demo GIF used above. |
| [`backend/bench/results/benchmark_results.json`](backend/bench/results/benchmark_results.json) | Machine-readable benchmark output. |

**About the benchmark.** CommonThreadBench is an *offline, synthetic* evaluation: it drives the real adapter, workflow and routes against Qloo-shaped mock responses, so its numbers describe this codebase's behaviour, not Qloo's accuracy or real-world taste. Live observations and human evaluation are kept separate and clearly tagged in the docs.

### Feedback and contributing

Found something confusing, or have an idea? Open an issue with the **Developer feedback** template ([new issue](https://github.com/HUNT-001/culture-engine/issues/new/choose)); it prompts for what you ran, what you expected and what happened. For code changes, branch from `main`, keep `pytest`, `npm test` and `npm run build` green, and use short conventional commit messages (`feat:`, `fix:`, `docs:`, `ci:`).

---

## Repository map

```text
.
├── backend/
│   ├── app/            FastAPI app: api/, core/, db/, domain/, providers/, services/, workflows/
│   ├── tests/          unit, API, lifecycle and benchmark tests
│   ├── bench/          CommonThreadBench (offline evaluation harness)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/            App.tsx, components/, lib/, api/, style.css, types.ts
│   └── .env.example
├── docs/               architecture, workflow, API contracts, benchmark, design-history/, assets/
├── .github/            CI workflows and the issue template
├── render.yaml         backend deployment blueprint
└── LICENSE             MIT
```

---

<div align="center">

**Common Thread** · where different tastes meet · built on [Qloo](https://docs.qloo.com/)'s cultural graph

</div>
