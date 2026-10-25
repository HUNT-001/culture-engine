"""Focused tests for the live Qloo HTTP adapter parsing and error handling.

Fixtures here are SYNTHETIC: they reproduce the real field *names* and *structure*
of the hackathon API (verified live on 2026-10) but contain only invented venue
names and IDs. No real Qloo response bodies are stored in this repository.
"""
import httpx
import pytest

from app.core.config import Settings
from app.providers.qloo import QlooClient, QlooProviderError


def _client_with_handler(handler) -> QlooClient:
    """Build a QlooClient whose transport is a local mock (no network, no real key)."""
    settings = Settings(qloo_api_key="test-key", mock_providers=False)
    client = QlooClient(settings)
    # Swap the live AsyncClient for one backed by a MockTransport, preserving base_url.
    client.client = httpx.AsyncClient(
        base_url=settings.qloo_base_url.rstrip("/"),
        transport=httpx.MockTransport(handler),
    )
    return client


# --- Synthetic payloads in the real response shape -------------------------------------

# Insights: {"success": true, "results": {"entities": [...]}, "query": {...}}
# Each place carries type="urn:entity", subtype="urn:entity:place", and a `query`
# object holding affinity + explainability when feature.explainability=true.
_SYNTHETIC_INSIGHTS = {
    "success": True,
    "results": {
        "entities": [
            {
                "name": "Synthetic Gallery",
                "entity_id": "00000000-0000-0000-0000-000000000001",
                "type": "urn:entity",
                "subtype": "urn:entity:place",
                "properties": {"address": "1 Example St, Testville"},
                "popularity": 0.91,
                "location": {"lat": 1.0, "lon": 2.0, "geohash": "xxxxxxx"},
                "query": {
                    "affinity": 0.87,
                    "explainability": {
                        "signal.interests.entities": [
                            {"entity_id": "AAAA-signal", "score": 1}
                        ]
                    },
                },
            },
            {
                "name": "Synthetic Cafe",
                "entity_id": "00000000-0000-0000-0000-000000000002",
                "type": "urn:entity",
                "subtype": "urn:entity:place",
                "properties": {"address": "2 Example Ave, Testville"},
                "popularity": 0.77,
                "query": {"affinity": 0.65},
            },
        ]
    },
    "query": {"localities": [], "explainability": {}},
}

# /search: {"results": [...]} with a `types` list on each entity.
_SYNTHETIC_SEARCH = {
    "results": [
        {
            "name": "Synthetic Artist",
            "entity_id": "00000000-0000-0000-0000-0000000000aa",
            "types": ["urn:entity:artist"],
            "properties": {},
            "popularity": 0.5,
        }
    ]
}


@pytest.mark.asyncio
async def test_parse_insights_places_uses_subtype_and_real_explainability():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/insights"
        # Signal and filter should be present on the outgoing request.
        q = request.url.params
        assert q.get("filter.type") == "urn:entity:place"
        assert q.get("signal.interests.entities")
        return httpx.Response(200, json=_SYNTHETIC_INSIGHTS)

    client = _client_with_handler(handler)
    try:
        candidates = await client.get_place_recommendations(
            ["AAAA-signal"], "Testville", take=5
        )
    finally:
        await client.close()

    assert len(candidates) == 2
    first = candidates[0]
    # Entity type must come from subtype, not the generic "urn:entity".
    assert first.entity_type == "urn:entity:place"
    assert first.address == "1 Example St, Testville"
    assert first.source == "qloo"
    assert first.verification_status == "unverified"
    # Real Qloo affinity + explainability are surfaced verbatim as evidence.
    assert isinstance(first.qloo_explanation, dict)
    assert first.qloo_explanation["affinity"] == 0.87
    assert "explainability" in first.qloo_explanation
    # An entity with affinity but no explainability block still keeps the affinity.
    assert candidates[1].qloo_explanation == {"affinity": 0.65}


@pytest.mark.asyncio
async def test_search_entities_parses_types_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        return httpx.Response(200, json=_SYNTHETIC_SEARCH)

    client = _client_with_handler(handler)
    try:
        entities = await client.search_entities("anything", take=1)
    finally:
        await client.close()

    assert len(entities) == 1
    assert entities[0]["entity_id"] == "00000000-0000-0000-0000-0000000000aa"
    assert entities[0]["entity_type"] == "urn:entity:artist"


@pytest.mark.asyncio
async def test_empty_entities_returns_empty_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "results": {"entities": []}})

    client = _client_with_handler(handler)
    try:
        candidates = await client.get_place_recommendations(["x"], "Testville")
    finally:
        await client.close()
    assert candidates == []


@pytest.mark.asyncio
async def test_no_signal_ids_makes_no_request():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls["n"] += 1
        return httpx.Response(200, json={})

    client = _client_with_handler(handler)
    try:
        candidates = await client.get_place_recommendations([], "Testville")
    finally:
        await client.close()
    assert candidates == []
    assert calls["n"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "QLOO_AUTH_ERROR", False),
        (403, "QLOO_AUTH_ERROR", False),
        (429, "QLOO_RATE_LIMIT", True),
        (500, "QLOO_UPSTREAM_ERROR", True),
        (400, "QLOO_BAD_REQUEST", False),
    ],
)
async def test_status_codes_map_to_provider_errors(status, code, retryable):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "irrelevant synthetic body"})

    client = _client_with_handler(handler)
    try:
        with pytest.raises(QlooProviderError) as exc_info:
            await client.get_place_recommendations(["x"], "Testville")
    finally:
        await client.close()
    assert exc_info.value.code == code
    assert exc_info.value.retryable is retryable


@pytest.mark.asyncio
async def test_invalid_json_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"not json", headers={"content-type": "application/json"}
        )

    client = _client_with_handler(handler)
    try:
        with pytest.raises(QlooProviderError) as exc_info:
            await client.search_entities("x")
    finally:
        await client.close()
    assert exc_info.value.code == "QLOO_INVALID_JSON"


@pytest.mark.asyncio
async def test_parsed_live_candidates_feed_ranking_engine():
    """Integration: parsed Qloo candidates flow through the deterministic ranking."""
    from app.services.ranking import merge_candidate_batches, rank_candidates, select_options

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_SYNTHETIC_INSIGHTS)

    client = _client_with_handler(handler)
    try:
        p1 = await client.get_place_recommendations(["sig-a"], "Testville")
        p2 = await client.get_place_recommendations(["sig-b"], "Testville")
    finally:
        await client.close()

    merged = merge_candidate_batches({"p1": p1, "p2": p2}, p1)
    ranked = rank_candidates(merged, ["p1", "p2"], "Testville")
    assert ranked
    # The shared place appears in both participant batches -> full coverage.
    top = ranked[0]
    assert top.group_coverage == 2
    assert top.maps_search_url.startswith("https://www.google.com/maps/search/")
    options = select_options(ranked, 2)
    assert options
    # Live candidates are never labelled demo.
    assert all(o.candidate.source == "qloo" for o in options)
