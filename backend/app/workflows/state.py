from typing import Any, TypedDict


class RecommendationState(TypedDict, total=False):
    request: dict[str, Any]
    _validated_request: dict[str, Any]
    run_id: str
    demo_mode: bool
    resolved_profiles: dict[str, list[dict[str, Any]]]
    unresolved_interests: list[str]
    participant_batches: dict[str, list[dict[str, Any]]]
    combined_batch: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    options: list[dict[str, Any]]
    warnings: list[str]
    query_count: int
    error_code: str
    provider_errors: list[str]
    excluded_entity_ids: list[str]
    status: str
