"""Qloo HTTP adapter.

IMPORTANT: Validate query parameter names and response fields against the current Qloo
hackathon documentation before using live mode. All version-specific handling belongs here.
"""
from typing import Any
import httpx
from app.core.config import Settings
from app.domain.schemas import Candidate


class QlooProviderError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class QlooClient:
    def __init__(self, settings: Settings):
        if not settings.qloo_api_key:
            raise ValueError("QLOO_API_KEY is required when MOCK_PROVIDERS=false")
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.qloo_base_url.rstrip("/"),
            timeout=settings.qloo_timeout_seconds,
            headers={"X-Api-Key": settings.qloo_api_key, "Accept": "application/json"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self.client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise QlooProviderError("QLOO_TIMEOUT", "Qloo request timed out.", True) from exc
        except httpx.HTTPError as exc:
            raise QlooProviderError("QLOO_NETWORK_ERROR", "Qloo request failed.", True) from exc

        if response.status_code in (401, 403):
            raise QlooProviderError("QLOO_AUTH_ERROR", "Qloo rejected the configured credentials.")
        if response.status_code == 429:
            raise QlooProviderError("QLOO_RATE_LIMIT", "Qloo request quota/rate limit reached.", True)
        if response.status_code >= 500:
            raise QlooProviderError("QLOO_UPSTREAM_ERROR", "Qloo service returned an error.", True)
        if response.status_code >= 400:
            # Do not leak provider response bodies to end users/logs.
            raise QlooProviderError("QLOO_BAD_REQUEST", "Qloo rejected the request; verify API parameters.")
        try:
            data = response.json()
        except ValueError as exc:
            raise QlooProviderError("QLOO_INVALID_JSON", "Qloo returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise QlooProviderError("QLOO_BAD_RESPONSE", "Unexpected Qloo response shape.")
        return data

    @staticmethod
    def _result_list(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize common collection wrappers; verify exact schema in live API tests."""
        current: Any = data.get("results", data.get("entities", []))
        if isinstance(current, dict):
            current = current.get("entities", current.get("results", current.get("items", [])))
        if not isinstance(current, list):
            return []
        return [item for item in current if isinstance(item, dict)]

    async def search_entities(self, query: str, take: int = 5) -> list[dict]:
        # The current hackathon docs may use version-specific parameter conventions.
        # Confirm `query` and `take` against your API guide before live execution.
        data = await self._get_json(self.settings.qloo_search_path, {"query": query, "take": take})
        entities: list[dict] = []
        for item in self._result_list(data):
            entity_id = item.get("entity_id") or item.get("id") or item.get("qid")
            name = item.get("name") or item.get("name_label") or item.get("label")
            if entity_id and name:
                entities.append({
                    "entity_id": str(entity_id),
                    "name": str(name),
                    "entity_type": item.get("type") or item.get("entity_type") or "unknown",
                    "raw": item,
                })
        return entities

    async def get_place_recommendations(
        self, entity_ids: list[str], location: str, take: int = 10
    ) -> list[Candidate]:
        clean_ids = list(dict.fromkeys(i for i in entity_ids if i))
        if not clean_ids:
            return []
        params: dict[str, Any] = {
            "filter.type": "urn:entity:place",
            "signal.interests.entities": ",".join(clean_ids),
            "filter.location.query": location,
            "take": take,
            "feature.explainability": "true",
        }
        data = await self._get_json(self.settings.qloo_insights_path, params)
        candidates: list[Candidate] = []
        for index, item in enumerate(self._result_list(data), start=1):
            entity_id = item.get("entity_id") or item.get("id") or item.get("qid")
            name = item.get("name") or item.get("name_label") or item.get("label")
            if not entity_id or not name:
                continue
            properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            address = properties.get("address") or item.get("address")
            explanation = item.get("explanation") or item.get("explainability") or item.get("features")
            candidates.append(Candidate(
                entity_id=str(entity_id),
                name=str(name),
                entity_type=str(item.get("type") or "urn:entity:place"),
                address=str(address) if address else None,
                source="qloo",
                combined_rank=None,
                qloo_explanation=explanation,
                verification_status="unverified",
            ))
        return candidates
