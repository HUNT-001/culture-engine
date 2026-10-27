# API Contracts

## `GET /api/health`
Returns `{status: "ok", environment, demo_mode}`; `demo_mode` is `true` when the backend runs on mock providers. Never returns credentials or environment dumps. In live mode (`MOCK_PROVIDERS=false`) without a `QLOO_API_KEY` the provider runtime cannot start, so this endpoint fails instead of silently serving mock data.

## `GET /api/entities/search`
The interest picker's source of candidates; the only route that calls Qloo's search. Query: `query` (2–100 characters, required) and `take` (1–8, default 5). Response: `{query, demo_mode, candidates: [{entity_id, name, entity_type, disambiguation?, source}]}` where `source` is `"qloo"` for a real Qloo entity and `"mock"` for a synthetic demo entity, which is never a real match. Errors: `422` invalid input; `503` retryable provider failure (timeout, rate limit, upstream error); `502` non-retryable provider failure (e.g. rejected credentials); no provider body or key is ever returned.

## `POST /api/recommendations`
Request shape:

```json
{
  "location": "Chennai, Tamil Nadu, India",
  "budget_per_person": 800,
  "budget_currency": "INR",
  "participants": [
    {"participant_id":"p1","display_name":"A","interests":["Radiohead","anime"],
     "resolved_interests":[{"text":"Radiohead","entity_id":"<id from /api/entities/search>","name":"Radiohead","entity_type":"urn:entity:artist"},
                           {"text":"anime","entity_id":"<id>","name":"Anime"}]},
    {"participant_id":"p2","display_name":"B","interests":["specialty coffee","indie films"],"resolved_interests":[...]}
  ]
}
```

Response (`RecommendationResponse`): `run_id`, `demo_mode`, `location`, `options` (each with ranking reasons, `evidence_labels`, Qloo affinity, `matched_interests` and a Maps search URL), `warnings`, `unresolved_interests`, a structured `needs_confirmation` list (`{participant_id, display_name, text}`) and `status` (`complete`, `partial` or `failed`). `demo_mode` is `true` for mock providers; mock venues carry `source: "mock"` and verification status `demo`, live venues are `unverified`.

**Entity confirmation (no silent matching).** The server binds an interest to a Qloo entity only when the request carries the user's explicit confirmation for it: a `resolved_interests` entry whose `text` equals the typed interest (case/whitespace-insensitive). Candidates come from `GET /api/entities/search`; the user picks one. An interest without a confirmation is never searched for, never taken from a first result and never accepted because a result's name matches exactly (one name can denote several entities). It is left out of the run and reported in `unresolved_interests` and `needs_confirmation`, a warning says so, and `status` is never `complete` while anything was left out. The typed wording and the confirmed `entity_id` are used exactly as sent. A run makes no `/search` request. The same rules apply to `POST /api/plans/{plan_id}/recommendations`, which uses the confirmations saved with each participant's preferences.

## Group plans (anonymous, expiring)

Tokens are random 256-bit values returned **once**; only SHA-256 hashes are stored. They travel in headers, never in URLs. Unknown plans and invalid tokens both return `404`; a missing token returns `401`; an expired plan returns `410`. Plans expire after `PLAN_TTL_HOURS` (default 24); creating a plan purges expired plans together with their participants, preferences and runs.

| Method & path | Auth header | Body | Success |
|---|---|---|---|
| `POST /api/plans` | — | `{location, budget_per_person?, budget_currency?}` | `201 {plan_id, share_token, expires_at}` |
| `POST /api/plans/{plan_id}/participants` | `X-Share-Token` | `{display_name}` | `201 {participant_id, participant_token}`; `409` when the plan has `MAX_PARTICIPANTS` (4) |
| `PUT /api/plans/{plan_id}/participants/{participant_id}/preferences` | `X-Participant-Token` | `{interests: 1–3, resolved_interests: 0–3 (confirmed entities, matched to interests by text), dislikes: 0–5}` (terms ≤100 chars, replaces previous) | `200` participant view |
| `GET /api/plans/{plan_id}` | `X-Share-Token` | — | `200` plan (incl. `budget_per_person`, `budget_currency`), participants with interests/dislikes, latest recommendation run (no tokens) |
| `POST /api/plans/{plan_id}/recommendations` | `X-Share-Token` | — | `200` `RecommendationResponse`, persisted as the latest run; `409` if fewer than two participants have interests |

Participants without interests are left out of a run with a warning. Dislikes are enforced as hard exclusions only for exact (case-insensitive) venue-name matches; a budget is recorded but cannot be checked against prices with the current data, and the response says so.

**Budget currency.** `budget_per_person` is a plain number (`> 0`, `≤ 100000`) and `budget_currency` is its ISO 4217 code, sent and stored separately (`50` + `USD`, never `"$50"`). Supported codes are listed in `backend/app/domain/currency.py` (INR, USD, GBP, EUR, CAD, AUD, NZD, JPY, CNY, SGD, HKD, AED, CHF, KRW, MXN, BRL, ZAR); codes are upper-cased and anything else is a `422`. The field is optional on every request and **defaults to `INR`**, so existing clients are unaffected, and a plan stored without a currency is returned as `INR`. A budget is only recorded: there is no currency conversion, the amount is never compared across currencies, and it does not influence ranking. The frontend suggests a currency from the destination (`frontend/src/lib/destination.ts`) and lets the user override it; the backend does not infer one.

## Error policy

- `422`: invalid input.
- `503`: required provider unavailable and no valid partial result (`/api/recommendations` and the plan run route; a plan run that returns `503` stores no run).
- `200` with `status: "failed"` and an empty `options` list: nothing could be recommended without a provider error, e.g. no interest was confirmed. A stored `failed` run does not mark the plan as recommended.
- `200` with warnings: valid but limited candidate set.
- Never return raw provider stack traces or secrets.

## Provider contract

- `QlooProvider.search_entities(query, take)` returns normalized entity matches.
- `QlooProvider.get_place_recommendations(entity_ids, location, take)` returns normalized place candidates plus explanation metadata where available.
- Provider response parsing stays in `app/providers/qloo.py`.
- Verify live query parameter names and response fields against Qloo's current hackathon API documentation before switching from mock mode.
