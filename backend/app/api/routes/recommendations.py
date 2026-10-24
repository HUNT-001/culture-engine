from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from app.domain.schemas import RecommendationRequest, RecommendationResponse
from app.providers.qloo import QlooProviderError
from app.services.runtime import get_runtime

router = APIRouter(tags=["recommendations"])


async def execute_workflow(runtime: dict, request: RecommendationRequest) -> RecommendationResponse:
    """Run the bounded workflow and map provider failures to the documented error policy."""
    run_id = str(uuid4())
    try:
        result = await runtime["graph"].ainvoke({"request": request.model_dump(), "run_id": run_id})
    except QlooProviderError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    except Exception as exc:
        # Avoid returning internal provider or stack-trace detail to the client.
        raise HTTPException(status_code=500, detail="Recommendation workflow failed. Try again.") from exc

    options = result.get("options", [])
    status = result.get("status", "partial" if options else "failed")
    provider_errors = result.get("provider_errors", [])
    if not options and provider_errors:
        # 503 only when the provider failed and there is no valid partial result.
        raise HTTPException(
            status_code=503,
            detail={"code": provider_errors[0], "message": "Cultural data provider is unavailable. Try again."},
        )
    return RecommendationResponse(
        run_id=result.get("run_id", run_id),
        demo_mode=bool(result.get("demo_mode", runtime["settings"].mock_providers)),
        location=request.location,
        options=options,
        warnings=result.get("warnings", []),
        unresolved_interests=result.get("unresolved_interests", []),
        status=status,
    )


@router.post("/recommendations", response_model=RecommendationResponse)
async def create_recommendations(request: RecommendationRequest, runtime: dict = Depends(get_runtime)):
    return await execute_workflow(runtime, request)
