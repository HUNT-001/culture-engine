from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import entities, health, plans, recommendations
from app.core.config import get_settings
from app.db.base import Base
from app.db.schema import ensure_schema
from app.db.session import engine
from app.db import models  # Ensure models are registered before create_all.

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenience for the starter. Use Alembic migrations for deployed schema changes.
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)  # additive column upgrades for databases from earlier releases
    yield
    from app.services.runtime import get_runtime
    runtime = get_runtime()
    close = getattr(runtime.get("qloo"), "close", None)
    if close is not None:
        await close()


app = FastAPI(
    title="Common Thread API",
    version="0.1.0",
    description="Qloo-grounded group cultural discovery starter API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Share-Token", "X-Participant-Token"],
)
app.include_router(health.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(entities.router, prefix="/api")


@app.get("/")
async def root():
    return {"service": "common-thread-api", "docs": "/docs"}
