from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def pick(client, text):
    """What the picker does: search, then explicitly choose a candidate for the typed text."""
    found = client.get("/api/entities/search", params={"query": text}).json()["candidates"][0]
    return {"text": text, "entity_id": found["entity_id"], "name": found["name"],
            "entity_type": found["entity_type"]}


def test_recommendations_mock_mode():
    with TestClient(app) as client:
        a, b = ["indie rock", "anime"], ["coffee", "illustration"]
        response = client.post("/api/recommendations", json={
            "location": "Chennai, Tamil Nadu, India",
            "participants": [
                {"participant_id": "p1", "display_name": "A", "interests": a,
                 "resolved_interests": [pick(client, t) for t in a]},
                {"participant_id": "p2", "display_name": "B", "interests": b,
                 "resolved_interests": [pick(client, t) for t in b]},
            ],
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["demo_mode"] is True
        assert body["options"]
