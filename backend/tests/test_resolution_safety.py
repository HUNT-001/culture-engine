"""Regression tests for entity-resolution safety (synthetic fixtures only; no Qloo calls).

Contract under test: the server never binds a typed interest to a Qloo entity on its own.
Not by taking the first search result, and not by an exact-name match (the same name can
denote several entities: a city, a band, an actor). Only an entity the user explicitly
confirmed is used, with the typed wording and the confirmed id passed through unchanged.
Everything else is excluded and reported in ``unresolved_interests`` and the structured
``needs_confirmation`` list. The stateless and the plan route must behave identically.
"""
import pytest

from app.core.config import get_settings
from app.domain.schemas import Candidate
from app.main import app
from app.providers.composer import DeterministicComposer
from app.services.runtime import get_runtime
from app.workflows.graph import build_recommendation_graph

# Synthetic homonyms: three entities named "Phoenix". The *band* is the one the user means,
# and it is deliberately NOT the first result.
CITY = {"entity_id": "syn:city:phoenix", "name": "Phoenix", "entity_type": "urn:entity:destination"}
BAND = {"entity_id": "syn:band:phoenix", "name": "Phoenix", "entity_type": "urn:entity:artist"}
ACTOR = {"entity_id": "syn:person:phoenix", "name": "Joaquin Phoenix",
         "entity_type": "urn:entity:person"}
SEARCH = {"phoenix": [CITY, BAND, ACTOR], "jazz": [{"entity_id": "syn:tag:jazz", "name": "Jazz"}]}


class SyntheticQloo:
    def __init__(self):
        self.searched: list[str] = []
        self.insights_calls: list[list[str]] = []

    async def search_entities(self, query: str, take: int = 5):
        self.searched.append(query)
        return SEARCH.get(query.strip().casefold(), [])

    async def get_place_recommendations(self, entity_ids, location, take=10):
        self.insights_calls.append(list(entity_ids))
        return [Candidate(entity_id=f"syn:venue:{i}", name=f"Synthetic Venue {i}", source="qloo",
                          qloo_explanation={"affinity": 0.9 - i / 10}) for i in range(4)]

    @property
    def sent_ids(self):
        return [e for call in self.insights_calls for e in call]


def confirm(text, entity):
    return {"text": text, **entity}


def person(pid, name, interests, confirmed=()):
    return {"participant_id": pid, "display_name": name, "interests": interests,
            "resolved_interests": list(confirmed)}


@pytest.fixture
def qloo():
    return SyntheticQloo()


@pytest.fixture
def stateless(client, qloo):
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    app.dependency_overrides[get_runtime] = lambda: {"settings": get_settings(), "graph": graph}

    def call(participants):
        res = client.post("/api/recommendations",
                          json={"location": "Synthetic City", "participants": participants})
        assert res.status_code == 200, res.text
        return res.json()
    return call


@pytest.fixture
def planned(client, qloo):
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    app.dependency_overrides[get_runtime] = lambda: {"settings": get_settings(), "graph": graph}

    def call(participants):
        plan = client.post("/api/plans", json={"location": "Synthetic City"}).json()
        share = {"X-Share-Token": plan["share_token"]}
        for p in participants:
            joined = client.post(f"/api/plans/{plan['plan_id']}/participants",
                                 json={"display_name": p["display_name"]}, headers=share).json()
            put = client.put(
                f"/api/plans/{plan['plan_id']}/participants/{joined['participant_id']}/preferences",
                json={"interests": p["interests"], "dislikes": [],
                      "resolved_interests": p["resolved_interests"]},
                headers={"X-Participant-Token": joined["participant_token"]})
            assert put.status_code == 200, put.text
        res = client.post(f"/api/plans/{plan['plan_id']}/recommendations", headers=share)
        assert res.status_code == 200, res.text
        return res.json()
    return call


ROUTES = pytest.mark.parametrize("route", ["stateless", "planned"])


def run(route, request, participants):
    return request.getfixturevalue(route)(participants)


@ROUTES
def test_exact_name_homonym_is_not_silently_bound(route, request, qloo):
    body = run(route, request, [person("p1", "Ana", ["Phoenix"]), person("p2", "Ben", ["jazz"])])
    assert qloo.searched == []                          # nothing is looked up by name
    assert qloo.sent_ids == []                          # no entity reaches Insights
    assert body["options"] == [] and body["status"] == "failed"
    assert body["unresolved_interests"] == ["Ana: Phoenix", "Ben: jazz"]
    assert {(u["display_name"], u["text"]) for u in body["needs_confirmation"]} == {
        ("Ana", "Phoenix"), ("Ben", "jazz")}
    assert any("not confirmed" in w for w in body["warnings"])


@ROUTES
def test_confirmed_id_is_used_exactly_not_the_first_homonym(route, request, qloo):
    body = run(route, request, [
        person("p1", "Ana", ["Phoenix"], [confirm("Phoenix", BAND)]),
        person("p2", "Ben", ["jazz"], [confirm("jazz", SEARCH["jazz"][0])]),
    ])
    assert body["status"] != "failed" and body["options"]
    assert body["needs_confirmation"] == [] and body["unresolved_interests"] == []
    assert BAND["entity_id"] in qloo.sent_ids
    assert CITY["entity_id"] not in qloo.sent_ids and ACTOR["entity_id"] not in qloo.sent_ids
    assert qloo.searched == []


@ROUTES
def test_partially_confirmed_group_uses_only_confirmed_and_is_never_complete(route, request, qloo):
    body = run(route, request, [
        person("p1", "Ana", ["Phoenix", "jazz"], [confirm("jazz", SEARCH["jazz"][0])]),
        person("p2", "Ben", ["jazz"], [confirm("jazz", SEARCH["jazz"][0])]),
    ])
    assert body["options"]
    assert body["unresolved_interests"] == ["Ana: Phoenix"]
    assert [u["text"] for u in body["needs_confirmation"]] == ["Phoenix"]
    assert CITY["entity_id"] not in qloo.sent_ids and BAND["entity_id"] not in qloo.sent_ids
    assert body["status"] == "partial"                  # something was excluded: not "complete"


@ROUTES
def test_no_qloo_request_at_all_when_nothing_is_confirmed(route, request, qloo):
    run(route, request, [person("p1", "Ana", ["Phoenix"]), person("p2", "Ben", ["Phoenix"])])
    assert qloo.searched == [] and qloo.insights_calls == []


@ROUTES
def test_confirmation_matches_typed_text_ignoring_case_and_spacing(route, request, qloo):
    body = run(route, request, [
        person("p1", "Ana", ["PHOENIX  "], [confirm("phoenix", BAND)]),
        person("p2", "Ben", ["jazz"], [confirm("Jazz", SEARCH["jazz"][0])]),
    ])
    assert body["needs_confirmation"] == [] and BAND["entity_id"] in qloo.sent_ids


@ROUTES
def test_confirmation_for_different_wording_does_not_carry_over(route, request, qloo):
    """If the user edits the text after confirming, the old confirmation no longer applies."""
    body = run(route, request, [
        person("p1", "Ana", ["Phoenix rising"], [confirm("Phoenix", BAND)]),
        person("p2", "Ben", ["jazz"], [confirm("jazz", SEARCH["jazz"][0])]),
    ])
    assert [u["text"] for u in body["needs_confirmation"]] == ["Phoenix rising"]
    assert BAND["entity_id"] not in qloo.sent_ids


def test_original_wording_and_confirmed_id_are_preserved_in_the_resolved_profile(qloo):
    import asyncio

    from app.domain.schemas import RecommendationRequest

    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "Synthetic City",
        "participants": [person("p1", "Ana", ["  Phoenix "], [confirm("phoenix", BAND)]),
                         person("p2", "Ben", ["jazz"], [confirm("jazz", SEARCH["jazz"][0])])]})
    state = asyncio.run(graph.ainvoke({"request": request.model_dump()}))
    entry = state["resolved_profiles"]["p1"][0]
    assert entry["input"] == "Phoenix"                  # the user's own wording (trimmed only)
    assert entry["entity_id"] == BAND["entity_id"] and entry["entity_type"] == BAND["entity_type"]


def test_confirmed_ids_are_persisted_and_survive_a_second_run(client, qloo):
    """Plan flow: confirmations saved with the preferences are reused on every later run."""
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    app.dependency_overrides[get_runtime] = lambda: {"settings": get_settings(), "graph": graph}
    plan = client.post("/api/plans", json={"location": "Synthetic City"}).json()
    share = {"X-Share-Token": plan["share_token"]}
    for name, term, ent in (("Ana", "Phoenix", BAND), ("Ben", "jazz", SEARCH["jazz"][0])):
        joined = client.post(f"/api/plans/{plan['plan_id']}/participants",
                             json={"display_name": name}, headers=share).json()
        client.put(f"/api/plans/{plan['plan_id']}/participants/{joined['participant_id']}/preferences",
                   json={"interests": [term], "resolved_interests": [confirm(term, ent)]},
                   headers={"X-Participant-Token": joined["participant_token"]})
    view = client.get(f"/api/plans/{plan['plan_id']}", headers=share).json()
    saved = {p["display_name"]: p["resolved_interests"] for p in view["participants"]}
    assert saved["Ana"][0]["entity_id"] == BAND["entity_id"]
    assert saved["Ana"][0]["text"] == "Phoenix"
    for _ in range(2):
        qloo.insights_calls.clear()
        res = client.post(f"/api/plans/{plan['plan_id']}/recommendations", headers=share).json()
        assert res["needs_confirmation"] == []
        assert BAND["entity_id"] in qloo.sent_ids and CITY["entity_id"] not in qloo.sent_ids
    assert qloo.searched == []


def test_a_run_that_used_nothing_does_not_mark_the_plan_recommended(client, qloo):
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    app.dependency_overrides[get_runtime] = lambda: {"settings": get_settings(), "graph": graph}
    plan = client.post("/api/plans", json={"location": "Synthetic City"}).json()
    share = {"X-Share-Token": plan["share_token"]}
    for name in ("Ana", "Ben"):
        joined = client.post(f"/api/plans/{plan['plan_id']}/participants",
                             json={"display_name": name}, headers=share).json()
        client.put(f"/api/plans/{plan['plan_id']}/participants/{joined['participant_id']}/preferences",
                   json={"interests": ["Phoenix"]},         # saved without any confirmation
                   headers={"X-Participant-Token": joined["participant_token"]})
    run = client.post(f"/api/plans/{plan['plan_id']}/recommendations", headers=share).json()
    assert run["status"] == "failed" and run["options"] == []
    view = client.get(f"/api/plans/{plan['plan_id']}", headers=share).json()
    assert view["status"] != "recommended"
    assert view["latest_recommendation"]["needs_confirmation"]      # still explains itself
