# API Contracts (initial)

## `GET /api/health`
Returns basic service health and whether providers are in mock mode. Never return credentials or environment dumps.

## `POST /api/recommendations`
Request shape:

```json
{
  "location": "Chennai, Tamil Nadu, India",
  "budget_per_person": 800,
  "participants": [
    {"participant_id":"p1","display_name":"A","interests":["Radiohead","anime"]},
    {"participant_id":"p2","display_name":"B","interests":["specialty coffee","indie films"]}
  ]
}
```

Response includes run ID, `demo_mode`, options, ranking reasons, source/evidence markers, Maps search URLs, warnings and unresolved interests.

## Group plans (anonymous, expiring)

Tokens are random 256-bit values returned **once**; only SHA-256 hashes are stored. They travel in headers, never in URLs. Unknown plans and invalid tokens both return `404`; a missing token returns `401`; an expired plan returns `410`. Plans expire after `PLAN_TTL_HOURS` (default 24); creating a plan purges expired plans together with their participants, preferences and runs.

| Method & path | Auth header | Body | Success |
|---|---|---|---|
| `POST /api/plans` | — | `{location, budget_per_person?}` | `201 {plan_id, share_token, expires_at}` |
| `POST /api/plans/{plan_id}/participants` | `X-Share-Token` | `{display_name}` | `201 {participant_id, participant_token}`; `409` when the plan has `MAX_PARTICIPANTS` (4) |
| `PUT /api/plans/{plan_id}/participants/{participant_id}/preferences` | `X-Participant-Token` | `{interests: 1–3, dislikes: 0–5}` (terms ≤100 chars, replaces previous) | `200` participant view |
| `GET /api/plans/{plan_id}` | `X-Share-Token` | — | `200` plan, participants with interests/dislikes, latest recommendation run (no tokens) |
| `POST /api/plans/{plan_id}/recommendations` | `X-Share-Token` | — | `200` `RecommendationResponse`, persisted as the latest run; `409` if fewer than two participants have interests |

Participants without interests are left out of a run with a warning. Dislikes are enforced as hard exclusions only for exact (case-insensitive) venue-name matches; a budget is recorded but cannot be checked against prices with the current data, and the response says so.

## Error policy

- `422`: invalid input.
- `503`: required provider unavailable and no valid partial result.
- `200` with warnings: valid but limited candidate set.
- Never return raw provider stack traces or secrets.

## Provider contract

- `QlooProvider.search_entities(query, take)` returns normalized entity matches.
- `QlooProvider.get_place_recommendations(entity_ids, location, take)` returns normalized place candidates plus explanation metadata where available.
- Provider response parsing stays in `app/providers/qloo.py`.
- Verify live query parameter names and response fields against Qloo's current hackathon API documentation before switching from mock mode.
