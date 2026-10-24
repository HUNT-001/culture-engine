import pytest
from app.domain.schemas import Candidate, RecommendationRequest
from app.providers.composer import DeterministicComposer
from app.providers.mock_qloo import MockQlooClient
from app.workflows.graph import build_recommendation_graph


@pytest.mark.asyncio
async def test_mock_workflow_returns_labeled_synthetic_options():
    graph = build_recommendation_graph(MockQlooClient(), DeterministicComposer(), demo_mode=True, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "Chennai, Tamil Nadu, India",
        "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["indie rock", "anime"]},
            {"participant_id": "p2", "display_name": "B", "interests": ["coffee", "illustration"]},
        ],
    })
    state = await graph.ainvoke({"request": request.model_dump()})
    assert state["demo_mode"] is True
    assert state["options"]
    assert all("Synthetic demo data" in " ".join(o["evidence_labels"]) for o in state["options"])


class FixedQloo:
    """Synthetic provider returning the same venues for everyone, so overlap is guaranteed."""

    async def search_entities(self, query: str, take: int = 5) -> list[dict]:
        return [{"entity_id": f"demo:interest:{query}", "name": query, "entity_type": "demo"}]

    async def get_place_recommendations(self, entity_ids, location, take=10):
        names = ["Demo Venue: Loud Bar", "Demo Venue: Quiet Gallery", "Demo Venue: Book Cafe"]
        return [Candidate(entity_id=f"demo:place:{i}", name=n, source="mock") for i, n in enumerate(names)]


def group(*people, budget=None):
    payload = {"location": "Bengaluru, Karnataka, India", "participants": list(people)}
    if budget:
        payload["budget_per_person"] = budget
    return RecommendationRequest.model_validate(payload).model_dump()


@pytest.mark.asyncio
async def test_disliked_venue_never_reaches_output():
    graph = build_recommendation_graph(FixedQloo(), DeterministicComposer(), demo_mode=True, max_calls=5)
    state = await graph.ainvoke({"request": group(
        {"participant_id": "p1", "display_name": "A", "interests": ["jazz"], "dislikes": ["demo venue: loud bar"]},
        {"participant_id": "p2", "display_name": "B", "interests": ["anime"]},
    )})
    names = [o["candidate"]["name"] for o in state["options"]]
    assert "Demo Venue: Loud Bar" not in names
    assert names
    assert any("stated dislike" in w for w in state["warnings"])


@pytest.mark.asyncio
async def test_shared_ground_when_everyone_overlaps_and_budget_is_flagged():
    graph = build_recommendation_graph(FixedQloo(), DeterministicComposer(), demo_mode=True, max_calls=5)
    state = await graph.ainvoke({"request": group(
        {"participant_id": "p1", "display_name": "A", "interests": ["jazz"]},
        {"participant_id": "p2", "display_name": "B", "interests": ["anime"]},
        budget=500,
    )})
    assert state["options"][0]["option_type"] == "shared_ground"
    assert any("Budget was recorded" in w for w in state["warnings"])


@pytest.mark.asyncio
async def test_unrepresented_participant_is_disclosed():
    class OneSidedQloo(FixedQloo):
        async def get_place_recommendations(self, entity_ids, location, take=10):
            if entity_ids == ["demo:interest:opera"]:
                return []
            return await super().get_place_recommendations(entity_ids, location, take)

    graph = build_recommendation_graph(OneSidedQloo(), DeterministicComposer(), demo_mode=True, max_calls=5)
    state = await graph.ainvoke({"request": group(
        {"participant_id": "p1", "display_name": "A", "interests": ["jazz"]},
        {"participant_id": "p2", "display_name": "B", "interests": ["opera"]},
    )})
    assert state["options"]
    assert all(o["option_type"] != "shared_ground" for o in state["options"])
    assert any("B's individual results" in w for w in state["warnings"])


@pytest.mark.asyncio
async def test_call_budget_skips_combined_query_with_warning():
    graph = build_recommendation_graph(FixedQloo(), DeterministicComposer(), demo_mode=True, max_calls=2)
    state = await graph.ainvoke({"request": group(
        {"participant_id": "p1", "display_name": "A", "interests": ["jazz"]},
        {"participant_id": "p2", "display_name": "B", "interests": ["anime"]},
    )})
    assert state["query_count"] == 2
    assert any("Combined-profile query skipped" in w for w in state["warnings"])
