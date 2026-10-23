# Internal Agent Workflow

## Nodes

`validate_request -> resolve_entities -> retrieve_insights -> normalize_candidates -> rank_options -> validate_evidence -> compose_response -> validate_output`

Conditional transitions:

- Invalid/missing required user inputs: return a validation error for the UI; don't call providers.
- Unresolvable interests: return an explicit unresolved-interest list.
- Too few candidates: allow at most one recovery attempt in later implementation; the current skeleton returns limited results with warnings.
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


## Known starter limitations

- Entity resolution currently selects the first returned search result. Add a user-facing entity confirmation step before public/live use, especially for ambiguous names.
- Plan/participant tables are scaffolding; the direct recommendation route is the only wired application flow.
- The initial LLM integration is explanation-only, not an unconstrained chat/agent loop.
- Real provider parameter names and response schemas need contract testing.
