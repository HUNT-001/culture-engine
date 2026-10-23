from functools import lru_cache
from app.core.config import get_settings
from app.providers.composer import build_composer
from app.providers.mock_qloo import MockQlooClient
from app.providers.qloo import QlooClient
from app.workflows.graph import build_recommendation_graph


@lru_cache(maxsize=1)
def get_runtime():
    settings = get_settings()
    if settings.mock_providers:
        qloo = MockQlooClient()
    else:
        qloo = QlooClient(settings)
    composer = build_composer(settings)
    graph = build_recommendation_graph(
        qloo=qloo,
        composer=composer,
        demo_mode=settings.mock_providers,
        max_calls=settings.qloo_max_insights_calls,
    )
    return {"settings": settings, "qloo": qloo, "composer": composer, "graph": graph}
