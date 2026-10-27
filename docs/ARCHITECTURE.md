# System Architecture

## System boundary

The frontend is untrusted. It may submit participant preferences and receive a structured result, but it never receives Qloo/LLM credentials or directly calls providers. FastAPI validates inputs and invokes a bounded LangGraph workflow. Qloo provides cultural candidates. The ranking engine owns fairness and diversity calculations. The response composer can explain validated results but cannot add candidates or alter rankings.

## Core modules

Diagrams of the full stack, the agent workflow and the scoring live in the root [`README.md`](../README.md).

1. `app/api/routes`: HTTP contract, request validation and response codes (`health`, `entities`, `recommendations`, `plans`).
2. `app/domain`: Pydantic schemas for requests, plans and recommendation results.
3. `app/workflows`: the typed LangGraph state, node functions and the fixed graph.
4. `app/providers`: provider interfaces, the Qloo `httpx` adapter, the demo mock and the response composer.
5. `app/services/resolution.py`: entity-resolution policy (only user-confirmed entities are bound).
6. `app/services/ranking.py`: deterministic per-person and group ranking, option selection.
7. `app/services/evidence.py` and `provenance.py`: mapping Qloo signals to the group's interests; live/demo labelling and Maps search links.
8. `app/services/runtime.py`: wires mock or live providers from settings.
9. `app/db`: SQLAlchemy models, engine/session and the plan repository (SQLite locally, PostgreSQL in production).
10. `app/core`: environment-driven settings and token hashing.

## Trust boundaries

- Never allow the LLM to provide raw URLs, headers, SQL or arbitrary tools.
- Only the Qloo adapter sends Qloo requests.
- Only the LLM composer formats explanations from validated facts.
- Ranking is deterministic and tested independently.
- A venue's cultural relevance does not establish opening hours, booking availability or safety.
- The initial app builds a Maps search link, not a verified directions/availability statement.

## Dependencies intentionally omitted

No vector DB, Redis, queue, microservices, long-term user profile system, payment integration or separate LangGraph persistence layer in v1. Add one only after a demonstrated requirement.
