import pytest
from app.domain.schemas import RecommendationRequest
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
