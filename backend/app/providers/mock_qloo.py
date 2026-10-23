"""Synthetic provider for local development and automated tests; never real Qloo data."""
from app.domain.schemas import Candidate


class MockQlooClient:
    async def search_entities(self, query: str, take: int = 5) -> list[dict]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        # Synthetic IDs: explicit demo prefix prevents confusion with real Qloo entities.
        return [{
            "entity_id": f"demo:interest:{normalized.replace(' ', '-')}",
            "name": query.strip(),
            "entity_type": "demo:entity",
            "raw": {"demo": True},
        }]

    async def get_place_recommendations(
        self, entity_ids: list[str], location: str, take: int = 10
    ) -> list[Candidate]:
        if not entity_ids:
            return []
        # Fictional names only: no claim that these places exist at this location.
        demo_places = [
            ("demo:place:01", "Demo Venue: The Listening Room"),
            ("demo:place:02", "Demo Venue: Art & Coffee Studio"),
            ("demo:place:03", "Demo Venue: Indie Culture Corner"),
            ("demo:place:04", "Demo Venue: The Creative Yard"),
            ("demo:place:05", "Demo Venue: Community Arts Space"),
            ("demo:place:06", "Demo Venue: The Discovery Lounge"),
            ("demo:place:07", "Demo Venue: Pop Culture Workshop"),
            ("demo:place:08", "Demo Venue: The Quiet Gallery"),
        ]
        # Rotate and limit the synthetic set by query input so local demos visibly differ.
        seed = sum(ord(ch) for entity_id in entity_ids for ch in entity_id)
        offset = seed % len(demo_places)
        rotated = demo_places[offset:] + demo_places[:offset]
        limit = min(4, max(1, take))
        return [Candidate(
            entity_id=eid,
            name=name,
            source="mock",
            combined_rank=None,
            verification_status="demo",
            qloo_explanation={"demo": True, "input_count": len(entity_ids)},
        ) for eid, name in rotated[:limit]]
