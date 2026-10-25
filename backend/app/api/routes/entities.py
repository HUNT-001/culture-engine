"""Server-side entity search for bounded user confirmation of interests.

All Qloo calls stay server-side; the client only ever receives minimal candidate fields.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.schemas import EntityCandidate, EntitySearchResponse
from app.providers.qloo import QlooProviderError
from app.services.runtime import get_runtime

router = APIRouter(tags=["entities"])

MAX_TAKE = 8


@router.get("/entities/search", response_model=EntitySearchResponse)
async def search_entities(
    query: str = Query(min_length=2, max_length=100),
    take: int = Query(default=5, ge=1, le=MAX_TAKE),
    runtime: dict = Depends(get_runtime),
):
    cleaned = query.strip()
    if len(cleaned) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters.")
    demo_mode = bool(runtime["settings"].mock_providers)
    try:
        raw = await runtime["qloo"].search_entities(cleaned, take=take)
    except QlooProviderError as exc:
        # Map provider failures to the documented policy; never leak provider internals.
        status = 503 if exc.retryable else 502
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except Exception as exc:  # noqa: BLE001 - defensive; do not leak internals
        raise HTTPException(status_code=500, detail="Entity search failed. Try again.") from exc

    source = "mock" if demo_mode else "qloo"
    candidates = [
        EntityCandidate(
            entity_id=str(item["entity_id"]),
            name=str(item["name"]),
            entity_type=str(item.get("entity_type") or "unknown"),
            disambiguation=item.get("disambiguation"),
            source=source,
        )
        for item in raw[:take]
        if item.get("entity_id") and item.get("name")
    ]
    return EntitySearchResponse(query=cleaned, demo_mode=demo_mode, candidates=candidates)
