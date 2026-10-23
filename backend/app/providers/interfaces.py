from typing import Protocol
from app.domain.schemas import Candidate


class QlooProvider(Protocol):
    async def search_entities(self, query: str, take: int = 5) -> list[dict]: ...
    async def get_place_recommendations(
        self, entity_ids: list[str], location: str, take: int = 10
    ) -> list[Candidate]: ...


class ComposerProvider(Protocol):
    async def compose(self, payload: dict) -> dict[str, str]: ...
