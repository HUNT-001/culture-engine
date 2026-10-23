from fastapi import APIRouter
from app.services.runtime import get_runtime

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    runtime = get_runtime()
    return {
        "status": "ok",
        "environment": runtime["settings"].app_env,
        "demo_mode": runtime["settings"].mock_providers,
    }
