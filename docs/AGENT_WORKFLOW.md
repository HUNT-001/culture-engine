# Internal Agent Workflow

## Nodes

`validate_request -> resolve_entities -> retrieve_insights -> normalize_candidates -> rank_options -> validate_evidence -> compose_response -> validate_output`

Conditional transitions:

- Invalid/missing required user inputs: return a validation error for the UI; don't call providers.
- Unresolvable interests: return an explicit unresolved-interest list.
- Too few candidates: allow at most one recovery attempt in later implementation; the current implementation returns limited results with warnings.
- Provider timeout/auth/quota failure: classify the error and return an honest partial/failure response.
- Invalid output: do not display it; use deterministic explanation fallback.

## State rules

- Keep run state JSON-compatible and bounded in size.
- Keep provider keys, database sessions and clients out of graph state; inject dependencies into node closures.
- Retain entity IDs, rank positions and source markers needed for auditability.
- Do not put unnecessary raw provider payloads in persisted state.
- Prefer ranks over raw scores across separate query requests unless comparability is documented and empirically verified.
- Label an option a "Cultural Bridge" only when source data supports cross-profile relevance; otherwise use a neutral alternative label.

## LLM policy

The LLM is optional and may compose explanations only from normalized candidate records and provenance. It must not invent venue details, infer protected traits, claim a user will definitely like a place, change hard constraints, or override ranking scores. Deterministic fallback works without an LLM key.

## Limits

- API calls per run: bounded by `MAX_INSIGHTS_CALLS`.
- HTTP timeout: configurable.
- Retries: avoid retrying non-transient failures (401/403, invalid parameters).
- Plan size: 2-4 participants for the initial product.
- Preferences: 1-3 interests per participant for the initial product.


## Known limitations

- Entity resolution binds only interests the user explicitly confirmed (via the entity picker). Unconfirmed interests are never searched, matched by name or taken from a first result; they are excluded and reported in `unresolved_interests` / `needs_confirmation`.
- Group plans (create, join, preferences, run) are fully wired and persisted; the stateless `/api/recommendations` route backs the same-device Quick Planner. The schema is created at startup (no migrations).
- Budget is recorded but cannot be enforced (no price data); dislikes are enforced only for exact venue-name matches.
- Only the first Qloo explanation per venue is kept when several participants' results contain it, so some linked interests are not displayed.
- The initial LLM integration is explanation-only, not an unconstrained chat/agent loop.
- The live Qloo adapter should be re-checked with the opt-in `backend/tests/test_qloo_live.py` (needs `QLOO_API_KEY` exported) after any API change.
