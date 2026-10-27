> **Historical.** This is the first build plan, written before implementation. Most items are done or have changed; it is kept for context and is not a status tracker. See the root `README.md` for the current system.

# Build Order / Definition of Done

## Milestone 0 — verify provider contract
- [ ] Confirm current hackathon search endpoint parameters and response shape.
- [ ] Make one search request, inspect the result and normalize a confirmed entity ID.
- [ ] Make one local-place Insights request, validate `filter.type`, location and explanation fields.
- [ ] Record request count and failure classes. Do not commit real response payloads or credentials.

## Milestone 1 — backend foundation
- [ ] Install `backend` package and run unit tests.
- [ ] Review SQLAlchemy models and create Alembic migrations before relying on persistent deployed data.
- [ ] Add request-size/rate limits, plan creation/join endpoints, and expiry/deletion.
- [ ] Add user-facing entity disambiguation instead of silently accepting ambiguous results.

## Milestone 2 — ranking correctness
- [ ] Add synthetic tests for all group sizes (2–4 participants).
- [ ] Test one participant being consistently underserved.
- [ ] Test no overlap, duplicate candidates, missing profile rankings and absent explainability.
- [ ] Ensure option labels downgrade to `alternative` when evidence does not support Shared Ground / Cultural Bridge / Stretch Choice.

## Milestone 3 — frontend / group experience
- [ ] Wire group creation to a shareable plan link.
- [ ] Add participant join, preference edit and consent-aware sharing.
- [ ] Add search-result confirmation for ambiguous Qloo entities.
- [ ] Show demo/live mode, source evidence, warnings and unverified venue fields.

## Milestone 4 — deployment and validation
- [ ] Deploy frontend and backend; set exact CORS origin.
- [ ] Configure provider secrets only in backend environment.
- [ ] Test cold start, timeout, quota exhaustion, malformed request and empty Qloo results.
- [ ] Compare the Qloo-grounded result against an LLM-only baseline using the same inputs.
- [ ] Confirm required Qloo licensing for production separately from hackathon access.
