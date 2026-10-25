"""Tests for GET /api/entities/search (bounded user confirmation)."""
from app.core.config import get_settings
from app.main import app
from app.services.runtime import get_runtime


class StubQloo:
    def __init__(self, results):
        self.results = results
        self.last_take = None

    async def search_entities(self, query: str, take: int = 5):
        self.last_take = take
        return self.results[:take]


def install(qloo, mock: bool):
    settings = get_settings().model_copy(update={"mock_providers": mock})
    app.dependency_overrides[get_runtime] = lambda: {"settings": settings, "qloo": qloo}


def test_search_returns_minimal_candidate_fields_live(client):
    qloo = StubQloo([
        {"entity_id": "E1", "name": "Radiohead", "entity_type": "urn:entity:artist",
         "disambiguation": "English rock band", "raw": {"secret": "hidden"}},
    ])
    install(qloo, mock=False)
    resp = client.get("/api/entities/search", params={"query": "radiohead"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["demo_mode"] is False
    assert len(body["candidates"]) == 1
    c = body["candidates"][0]
    assert c == {
        "entity_id": "E1", "name": "Radiohead", "entity_type": "urn:entity:artist",
        "disambiguation": "English rock band", "source": "qloo",
    }
    # raw provider fields must not leak through.
    assert "raw" not in c and "secret" not in resp.text


def test_search_marks_mock_candidates_as_mock(client):
    qloo = StubQloo([{"entity_id": "demo:x", "name": "Demo", "entity_type": "demo:entity"}])
    install(qloo, mock=True)
    resp = client.get("/api/entities/search", params={"query": "anything"})
    body = resp.json()
    assert body["demo_mode"] is True
    assert body["candidates"][0]["source"] == "mock"


def test_search_bounds_take(client):
    qloo = StubQloo([{"entity_id": str(i), "name": f"n{i}"} for i in range(20)])
    install(qloo, mock=False)
    resp = client.get("/api/entities/search", params={"query": "many", "take": 50})
    assert resp.status_code == 422  # take above the max is rejected
    resp2 = client.get("/api/entities/search", params={"query": "many", "take": 8})
    assert resp2.status_code == 200
    assert len(resp2.json()["candidates"]) == 8
    assert qloo.last_take == 8


def test_search_rejects_short_query(client):
    resp = client.get("/api/entities/search", params={"query": "a"})
    assert resp.status_code == 422


def test_search_in_default_mock_mode_returns_demo_entities(client):
    # No runtime override: conftest runs the app in real mock mode end to end.
    resp = client.get("/api/entities/search", params={"query": "indie rock"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["demo_mode"] is True
    assert body["candidates"], "mock provider should return at least one demo candidate"
    assert all(c["source"] == "mock" for c in body["candidates"])
