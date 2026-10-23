from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    mock_providers: bool = True
    database_url: str = "sqlite:///./common_thread.db"
    cors_origins: str = "http://localhost:5173"

    qloo_api_key: str = ""
    qloo_base_url: str = "https://hackathon.api.qloo.com"
    qloo_search_path: str = "/search"
    qloo_insights_path: str = "/v2/insights"
    qloo_timeout_seconds: float = 15.0
    qloo_max_insights_calls: int = 5

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 15.0

    plan_ttl_hours: int = 24
    max_participants: int = 4
    max_interests_per_participant: int = 3
    default_candidate_take: int = Field(default=10, ge=3, le=20)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
