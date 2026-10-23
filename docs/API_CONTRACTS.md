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
