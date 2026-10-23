from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_recommendations_mock_mode():
    with TestClient(app) as client:
        response = client.post("/api/recommendations", json={
            "location": "Chennai, Tamil Nadu, India",
            "participants": [
                {"participant_id": "p1", "display_name": "A", "interests": ["indie rock", "anime"]},
                {"participant_id": "p2", "display_name": "B", "interests": ["coffee", "illustration"]},
            ],
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["demo_mode"] is True
        assert body["options"]
