# Common Thread — Qloo Hackathon Starter

A modular-monolith starter for a culturally grounded group-experience planner. The skeleton uses React + Vite, FastAPI, LangGraph, SQLAlchemy/PostgreSQL, a Qloo adapter, and a deterministic group-ranking engine.

> **Status:** starter scaffold, not a finished production app. The mock provider lets the app and tests run without credentials. Live Qloo endpoint parameters and response shapes must be validated against the current Qloo hackathon docs and your own API responses before relying on real data.

## Architecture choices

- **Frontend:** React + Vite + TypeScript.
- **Backend:** FastAPI and Pydantic.
- **Agent workflow:** LangGraph `StateGraph`; one bounded workflow, not a swarm.
- **Persistence:** SQLAlchemy models, local SQLite by default, Postgres URL supported.
- **Cultural data:** Qloo behind `QlooClient` interface.
- **Ranking:** deterministic Python, independent of the LLM.
- **Text generation:** `Composer` interface. Deterministic composer by default; optional OpenAI-compatible chat completions endpoint.
- **Place verification:** deliberately deferred. MVP creates Maps search links and does not claim current opening hours/availability.

## 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Git
- Optional: Qloo hackathon API key
- Optional: an API key for an OpenAI-compatible LLM provider
- Optional: hosted PostgreSQL URL (Supabase or another compatible provider)

## 2. Run backend (mock mode)

From the repository root:

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env  # PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The starter defaults to `MOCK_PROVIDERS=true`; recommendations will be marked as demo data. The current frontend submits a group directly; database models are included as foundations for the share-link plan flow, which still needs its plan CRUD/join routes implemented. Swagger UI: `http://localhost:8000/docs`.

## 3. Run frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local  # PowerShell: Copy-Item .env.example .env.local
npm run dev
```

Open the URL Vite prints, usually `http://localhost:5173`.

## 4. Enable live Qloo

1. Read the official [Qloo API docs](https://docs.qloo.com/) and the hackathon developer guide.
2. Set `MOCK_PROVIDERS=false` and `QLOO_API_KEY` in `backend/.env` only.
3. Verify `QLOO_BASE_URL`, search parameters, Insights parameters and response parsing in `backend/app/providers/qloo.py` against the exact current hackathon API docs. The adapter is deliberately isolated because endpoint conventions/response shapes can differ by API version.
4. Test entity resolution and a single Insights query before trying a whole group workflow.
5. Never commit `.env`, live Qloo payloads, API keys, or private response caches.

The current adapter assumes a Qloo search route `/search` and Insights route `/v2/insights`, with parameters isolated in that file. Do not treat this assumption as verified until you test it against the hackathon API environment.

## 5. Optional LLM provider

The app does not require an LLM to run in mock mode. To enable the optional OpenAI-compatible composer, configure `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `backend/.env`. This starter uses the chat-completions HTTP contract; verify that your selected provider supports it. LLM output is restricted to explanations; it cannot change the ranking or invent candidate facts.

## 6. Test

```bash
cd backend
pytest
```

Tests use synthetic fixtures and a mock Qloo provider. Do not commit Qloo's real response payloads as fixtures unless the event terms explicitly allow redistribution.

## 7. Deployment outline

- Frontend: Cloudflare Pages, build command `npm run build`, output directory `dist`, root `frontend`.
- Backend: Render web service, root `backend`, build `pip install -e .`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Database: hosted PostgreSQL, set `DATABASE_URL` in backend service. Use a URL accepted by SQLAlchemy; for psycopg 3 use `postgresql+psycopg://...`.
- Set `CORS_ORIGINS` to the exact deployed frontend origin.
- Configure secrets in the host dashboard, not in frontend environment variables.
- Free-tier uptime, quotas, sleep behavior and availability are not guaranteed; test cold starts and use quota limits.

## 8. Before public launch

- Replace default development secret and enable secure share-token handling.
- Add Alembic migrations rather than relying on `create_all` for schema changes.
- Set retention/deletion policy for plans and preferences.
- Rate-limit plan creation and recommendations.
- Review Qloo licensing/production access separately from hackathon access.
- Add integration tests for actual live API responses without exposing secrets.
- Clearly label unverified hours, event schedules and availability.

## Repository map

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md), and [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) before extending the implementation.
