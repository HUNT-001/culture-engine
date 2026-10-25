from datetime import timedelta
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import hash_token
from app.db import repository as repo
from app.db.models import PlanModel, RecommendationRunModel
from app.db.session import SessionLocal
from app.domain.schemas import Candidate
from app.main import app
from app.providers.composer import DeterministicComposer
from app.providers.qloo import QlooProviderError
from app.services.runtime import get_runtime
from app.workflows.graph import build_recommendation_graph


def create_plan(client, **overrides):
    body = {"location": "Chennai, Tamil Nadu, India", "budget_per_person": 800, **overrides}
    response = client.post("/api/plans", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def join(client, plan, name):
    response = client.post(
        f"/api/plans/{plan['plan_id']}/participants",
        json={"display_name": name},
        headers={"X-Share-Token": plan["share_token"]},
    )
    return response


def set_prefs(client, plan, participant, interests, dislikes=None):
    return client.put(
        f"/api/plans/{plan['plan_id']}/participants/{participant['participant_id']}/preferences",
        json={"interests": interests, "dislikes": dislikes or []},
        headers={"X-Participant-Token": participant["participant_token"]},
    )


def ready_plan(client):
    plan = create_plan(client)
    a = join(client, plan, "Asha").json()
    b = join(client, plan, "Ben").json()
    assert set_prefs(client, plan, a, ["indie rock", "anime"]).status_code == 200
    assert set_prefs(client, plan, b, ["specialty coffee", "illustration"]).status_code == 200
    return plan, a, b


def install_runtime(qloo):
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=True, max_calls=5)
    app.dependency_overrides[get_runtime] = lambda: {"settings": get_settings(), "graph": graph}


# --- lifecycle and persistence ----------------------------------------------------------


def test_plan_lifecycle_persists_participants_and_preferences(client):
    plan, a, b = ready_plan(client)
    response = client.get(f"/api/plans/{plan['plan_id']}", headers={"X-Share-Token": plan["share_token"]})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["max_participants"] == 4
    assert [p["display_name"] for p in body["participants"]] == ["Asha", "Ben"]
    assert body["participants"][0]["interests"] == ["indie rock", "anime"]
    assert body["latest_recommendation"] is None
    # No raw or hashed token is ever echoed back in the plan view.
    text = response.text
    assert plan["share_token"] not in text and a["participant_token"] not in text
    assert "token" not in text


def test_tokens_are_stored_only_as_hashes(client):
    plan = create_plan(client)
    participant = join(client, plan, "Asha").json()
    with SessionLocal() as db:
        stored = db.get(PlanModel, plan["plan_id"])
        assert stored.share_token_hash == hash_token(plan["share_token"])
        assert stored.share_token_hash != plan["share_token"]
        assert stored.participants[0].join_token_hash == hash_token(participant["participant_token"])


def test_preferences_can_be_replaced(client):
    plan = create_plan(client)
    a = join(client, plan, "Asha").json()
    set_prefs(client, plan, a, ["jazz"], ["karaoke"])
    response = set_prefs(client, plan, a, ["anime", "anime ", "  "], [])
    assert response.status_code == 200
    assert response.json()["interests"] == ["anime"]
    assert response.json()["dislikes"] == []


def test_end_to_end_mock_run_is_persisted_and_retrievable(client):
    plan, _, _ = ready_plan(client)
    headers = {"X-Share-Token": plan["share_token"]}
    response = client.post(f"/api/plans/{plan['plan_id']}/recommendations", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["demo_mode"] is True
    assert result["options"]
    for option in result["options"]:
        coverage = option["candidate"]["group_coverage"]
        assert option["candidate"]["verification_status"] == "demo"
        # Labels must be backed by the evidence that defines them.
        if option["option_type"] == "shared_ground":
            assert coverage == 2
        if option["option_type"] == "cultural_bridge":
            assert 1 < coverage < 2
        if option["option_type"] == "stretch_choice":
            assert option["candidate"]["combined_rank"] is not None and coverage <= 1
    assert any("Budget was recorded" in w for w in result["warnings"])

    stored = client.get(f"/api/plans/{plan['plan_id']}", headers=headers).json()
    assert stored["status"] == "recommended"
    assert stored["latest_recommendation"]["run_id"] == result["run_id"]


# --- access control, limits and expiry ---------------------------------------------------


def test_invalid_or_missing_share_token_is_rejected(client):
    plan = create_plan(client)
    url = f"/api/plans/{plan['plan_id']}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Share-Token": "wrong"}).status_code == 404
    assert client.get("/api/plans/does-not-exist", headers={"X-Share-Token": plan["share_token"]}).status_code == 404
    other = create_plan(client)
    assert client.get(url, headers={"X-Share-Token": other["share_token"]}).status_code == 404


def test_participant_token_is_bound_to_its_participant(client):
    plan = create_plan(client)
    a = join(client, plan, "Asha").json()
    b = join(client, plan, "Ben").json()
    forged = {"participant_id": a["participant_id"], "participant_token": b["participant_token"]}
    assert set_prefs(client, plan, forged, ["jazz"]).status_code == 404
    missing = client.put(
        f"/api/plans/{plan['plan_id']}/participants/{a['participant_id']}/preferences",
        json={"interests": ["jazz"]},
    )
    assert missing.status_code == 401


def test_participant_limit_is_enforced(client):
    plan = create_plan(client)
    for index in range(4):
        assert join(client, plan, f"Friend {index}").status_code == 201
    response = join(client, plan, "Fifth")
    assert response.status_code == 409


def test_expired_plan_returns_gone_and_is_purged(client):
    plan = create_plan(client)
    with SessionLocal() as db:
        stored = db.get(PlanModel, plan["plan_id"])
        stored.expires_at = repo.utc_now() - timedelta(minutes=1)
        db.add(RecommendationRunModel(plan_id=stored.id, status="complete", result_json={}))
        db.commit()
    headers = {"X-Share-Token": plan["share_token"]}
    assert client.get(f"/api/plans/{plan['plan_id']}", headers=headers).status_code == 410
    assert join(client, plan, "Late").status_code == 410

    create_plan(client)  # Creating a plan purges expired ones.
    with SessionLocal() as db:
        assert db.get(PlanModel, plan["plan_id"]) is None
        runs = db.scalars(select(RecommendationRunModel).where(RecommendationRunModel.plan_id == plan["plan_id"]))
        assert runs.first() is None


def test_recommendations_need_two_ready_participants(client):
    plan = create_plan(client)
    a = join(client, plan, "Asha").json()
    join(client, plan, "Ben")
    set_prefs(client, plan, a, ["jazz"])
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 409


def test_participants_without_interests_are_excluded_with_warning(client):
    plan, _, _ = ready_plan(client)
    join(client, plan, "Late arrival")
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 200
    assert any("not added interests" in w for w in response.json()["warnings"])


# --- malformed requests -----------------------------------------------------------------


def test_malformed_plan_requests_are_rejected(client):
    assert client.post("/api/plans", json={"location": " "}).status_code == 422
    assert client.post("/api/plans", json={"location": "Chennai", "budget_per_person": -5}).status_code == 422
    assert client.post("/api/plans", json={"location": "Chennai", "admin": True}).status_code == 422
    plan = create_plan(client)
    assert join(client, plan, "   ").status_code == 422
    a = join(client, plan, "Asha").json()
    assert set_prefs(client, plan, a, []).status_code == 422
    assert set_prefs(client, plan, a, ["  ", ""]).status_code == 422
    assert set_prefs(client, plan, a, ["a", "b", "c", "d"]).status_code == 422
    assert set_prefs(client, plan, a, ["x" * 101]).status_code == 422


def test_malformed_direct_recommendation_requests_are_rejected(client):
    person = {"participant_id": "p1", "display_name": "A", "interests": ["jazz"]}
    url = "/api/recommendations"
    assert client.post(url, json={"location": "Chennai", "participants": [person]}).status_code == 422
    assert client.post(url, json={"location": "Chennai", "participants": [person, person]}).status_code == 422
    five = [{**person, "participant_id": f"p{i}"} for i in range(5)]
    assert client.post(url, json={"location": "Chennai", "participants": five}).status_code == 422
    blank = {**person, "participant_id": "p2", "interests": ["  "]}
    assert client.post(url, json={"location": "Chennai", "participants": [person, blank]}).status_code == 422


# --- provider failures ------------------------------------------------------------------


class FailingQloo:
    def __init__(self, code: str, fail_terms: set[str] | None = None):
        self.code = code
        self.fail_terms = fail_terms

    async def search_entities(self, query: str, take: int = 5) -> list[dict]:
        if self.fail_terms is None or query in self.fail_terms:
            raise QlooProviderError(self.code, "simulated failure", retryable=True)
        return [{"entity_id": f"demo:interest:{query}", "name": query, "entity_type": "demo"}]

    async def get_place_recommendations(self, entity_ids, location, take=10):
        return [
            Candidate(entity_id=f"demo:place:{i}", name=f"Demo Venue {i}", source="mock", verification_status="demo")
            for i in range(4)
        ]


def test_auth_failure_returns_503_without_leaking_details(client):
    plan, _, _ = ready_plan(client)
    install_runtime(FailingQloo("QLOO_AUTH_ERROR"))
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "QLOO_AUTH_ERROR"
    assert "Traceback" not in response.text


def test_total_lookup_outage_returns_503(client):
    plan, _, _ = ready_plan(client)
    install_runtime(FailingQloo("QLOO_TIMEOUT"))
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "QLOO_TIMEOUT"
    with SessionLocal() as db:
        assert db.get(PlanModel, plan["plan_id"]).status == "created"


def test_partial_lookup_failure_degrades_with_warning(client):
    plan, _, _ = ready_plan(client)
    install_runtime(FailingQloo("QLOO_TIMEOUT", fail_terms={"anime"}))
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["options"]
    assert "Asha: anime" in body["unresolved_interests"]
    assert any("provider failed" in w for w in body["warnings"])
