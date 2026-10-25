"""Opt-in live contract check against the Qloo hackathon API.

Skipped unless QLOO_API_KEY is exported in the shell environment (a key in backend/.env alone
does not enable it). Makes at most two requests. It checks the adapter's *assumed* parameters
and prints only counts, never response bodies; a failure here means the adapter assumptions
need correcting, not that the API is broken.
"""
import os
import pytest
from app.core.config import Settings
from app.providers.qloo import QlooClient

pytestmark = pytest.mark.skipif(not os.getenv("QLOO_API_KEY"), reason="QLOO_API_KEY not set; live Qloo test skipped")


@pytest.mark.asyncio
async def test_live_search_then_place_insights():
    settings = Settings(mock_providers=False, qloo_api_key=os.environ["QLOO_API_KEY"])
    client = QlooClient(settings)
    try:
        entities = await client.search_entities("Radiohead", take=3)
        assert entities, "Search returned no entities; verify /search parameters and response shape."
        assert all(e["entity_id"] and e["name"] for e in entities)

        location = os.getenv("QLOO_LIVE_TEST_LOCATION", "Chennai, Tamil Nadu, India")
        candidates = await client.get_place_recommendations([entities[0]["entity_id"]], location, take=5)
        # HTTP 200 with an empty list is a known failure mode (unsupported params are ignored).
        assert candidates, "Insights returned no places; verify the location filter parameter for urn:entity:place."
        print(f"live search entities={len(entities)} places={len(candidates)}")
    finally:
        await client.close()
