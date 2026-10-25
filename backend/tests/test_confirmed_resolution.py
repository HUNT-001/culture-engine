"""Workflow-level resolution correctness: confirmed entities bypass search; unconfirmed
interests are auto-accepted only on an exact name match, never a silent first result."""
import pytest

from app.domain.schemas import Candidate, RecommendationRequest
from app.providers.composer import DeterministicComposer
from app.workflows.graph import build_recommendation_graph


class FakeQloo:
    """Records search queries and the entity IDs that reach the Insights call."""
    def __init__(self, search_results: dict[str, list[dict]]):
        self.search_results = search_results
        self.searched: list[str] = []
        self.insights_calls: list[list[str]] = []

    async def search_entities(self, query: str, take: int = 5) -> list[dict]:
        self.searched.append(query)
        return self.search_results.get(query.strip().casefold(), [])

    async def get_place_recommendations(self, entity_ids, location, take=10) -> list[Candidate]:
        self.insights_calls.append(list(entity_ids))
        return [
            Candidate(entity_id=f"place:{'-'.join(entity_ids)[:12] or 'none'}", name="Venue",
                      source="qloo", qloo_explanation={"affinity": 0.8})
        ]


@pytest.mark.asyncio
async def test_confirmed_interest_is_used_without_searching():
    qloo = FakeQloo(search_results={})  # no search results available at all
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "New York",
        "participants": [
            {"participant_id": "p1", "display_name": "Ana",
             "interests": ["independent film"],
             "resolved_interests": [{"text": "independent film", "entity_id": "ENT-CHOSEN",
                                     "name": "Independent Film", "entity_type": "urn:tag"}]},
            {"participant_id": "p2", "display_name": "Ben", "interests": ["jazz"],
             "resolved_interests": [{"text": "jazz", "entity_id": "ENT-JAZZ", "name": "Jazz"}]},
        ],
    })
    await graph.ainvoke({"request": request.model_dump()})
    # The confirmed interest never triggers a search, and its chosen id reaches Insights.
    assert qloo.searched == []
    flat_ids = [eid for call in qloo.insights_calls for eid in call]
    assert "ENT-CHOSEN" in flat_ids and "ENT-JAZZ" in flat_ids


@pytest.mark.asyncio
async def test_unconfirmed_exact_match_is_auto_accepted():
    qloo = FakeQloo(search_results={
        "indie rock": [{"entity_id": "IR", "name": "Indie Rock", "entity_type": "urn:tag"}],
        "jazz": [{"entity_id": "JZ", "name": "Jazz"}],
    })
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "New York",
        "participants": [
            {"participant_id": "p1", "display_name": "Ana", "interests": ["indie rock"]},
            {"participant_id": "p2", "display_name": "Ben", "interests": ["jazz"]},
        ],
    })
    state = await graph.ainvoke({"request": request.model_dump()})
    assert state["unresolved_interests"] == []
    flat_ids = [eid for call in qloo.insights_calls for eid in call]
    assert "IR" in flat_ids and "JZ" in flat_ids


@pytest.mark.asyncio
async def test_ambiguous_result_is_left_unresolved_not_first_match():
    # Search returns a plausible-but-non-exact entity; it must NOT be silently accepted.
    qloo = FakeQloo(search_results={
        "independent film": [
            {"entity_id": "DOC", "name": "The Independent Film Handbook"},
        ],
        "jazz": [{"entity_id": "JZ", "name": "Jazz"}],
    })
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "New York",
        "participants": [
            {"participant_id": "p1", "display_name": "Ana", "interests": ["independent film"]},
            {"participant_id": "p2", "display_name": "Ben", "interests": ["jazz"]},
        ],
    })
    state = await graph.ainvoke({"request": request.model_dump()})
    # The non-exact match is reported unresolved, and its id never reaches Insights.
    assert any("independent film" in u for u in state["unresolved_interests"])
    flat_ids = [eid for call in qloo.insights_calls for eid in call]
    assert "DOC" not in flat_ids
    assert "JZ" in flat_ids  # the exact one still goes through


@pytest.mark.asyncio
async def test_confirmed_overlay_for_other_text_does_not_apply():
    # A confirmed entity whose text doesn't match the interest must not be used for it.
    qloo = FakeQloo(search_results={"jazz": [{"entity_id": "JZ", "name": "Jazz"}]})
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    request = RecommendationRequest.model_validate({
        "location": "New York",
        "participants": [
            {"participant_id": "p1", "display_name": "Ana", "interests": ["opera"],
             "resolved_interests": [{"text": "jazz", "entity_id": "JZ", "name": "Jazz"}]},
            {"participant_id": "p2", "display_name": "Ben", "interests": ["jazz"]},
        ],
    })
    state = await graph.ainvoke({"request": request.model_dump()})
    # "opera" has no confirmation and no exact search match -> unresolved; JZ not misapplied to it.
    assert any("opera" in u for u in state["unresolved_interests"])
