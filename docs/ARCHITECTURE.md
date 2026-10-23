# System Architecture

## System boundary

The frontend is untrusted. It may submit participant preferences and receive a structured result, but it never receives Qloo/LLM credentials or directly calls providers. FastAPI validates inputs and invokes a bounded LangGraph workflow. Qloo provides cultural candidates. The ranking engine owns fairness and diversity calculations. The response composer can explain validated results but cannot add candidates or alter rankings.

## Core modules

1. `app/api`: HTTP contract, request validation and response codes.
2. `app/domain`: Pydantic domain schemas and immutable recommendation structures.
3. `app/workflows`: typed LangGraph state, nodes and conditional transitions.
4. `app/providers`: adapter interfaces and provider-specific HTTP behavior.
5. `app/services/ranking.py`: deterministic ranking algorithm.
6. `app/services/provenance.py`: source/evidence checks and Maps links.
7. `app/db`: SQLAlchemy models, engine/session and repository boundaries.

## Trust boundaries

- Never allow the LLM to provide raw URLs, headers, SQL or arbitrary tools.
- Only the Qloo adapter sends Qloo requests.
- Only the LLM composer formats explanations from validated facts.
- Ranking is deterministic and tested independently.
- A venue's cultural relevance does not establish opening hours, booking availability or safety.
- The initial app builds a Maps search link, not a verified directions/availability statement.

## Dependencies intentionally omitted

No vector DB, Redis, queue, microservices, long-term user profile system, payment integration or separate LangGraph persistence layer in v1. Add one only after a demonstrated requirement.
