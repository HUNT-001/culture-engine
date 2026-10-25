from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

MAX_TERM_LENGTH = 100


def _clean_terms(values: list[str], info: ValidationInfo) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if any(len(value) > MAX_TERM_LENGTH for value in cleaned):
        raise ValueError(f"each term must be at most {MAX_TERM_LENGTH} characters")
    if info.field_name == "interests" and not cleaned:
        raise ValueError("at least one non-blank interest is required")
    # Deduplicate while preserving the user's order.
    return list(dict.fromkeys(cleaned))


def _clean_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=60)
    interests: list[str] = Field(min_length=1, max_length=3)
    dislikes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("interests", "dislikes")
    @classmethod
    def clean_terms(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return _clean_terms(values, info)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: str = Field(min_length=2, max_length=160)
    budget_per_person: float | None = Field(default=None, gt=0, le=100000)
    participants: list[ParticipantInput] = Field(min_length=2, max_length=4)

    @field_validator("location")
    @classmethod
    def clean_location(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def check_unique_participants(self):
        ids = [p.participant_id for p in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("participant_id values must be unique")
        return self


class Candidate(BaseModel):
    entity_id: str
    name: str
    entity_type: str = "urn:entity:place"
    address: str | None = None
    source: Literal["qloo", "mock"] = "qloo"
    participant_ranks: dict[str, int] = Field(default_factory=dict)
    # Raw Qloo-provided affinity per participant query (evidence, not our score). Only
    # populated when the live API returns a numeric `query.affinity`; empty in mock mode.
    participant_affinities: dict[str, float] = Field(default_factory=dict)
    combined_rank: int | None = None
    qloo_explanation: Any | None = None
    # Highest Qloo affinity across participant queries, surfaced for traceability.
    # This is a Qloo signal, distinct from our heuristic `rank_score`.
    qloo_affinity: float | None = None
    verification_status: Literal["unverified", "verified", "ambiguous", "demo"] = "unverified"
    maps_search_url: str | None = None
    rank_score: float = 0.0
    group_coverage: int = 0
    reasons: list[str] = Field(default_factory=list)


class RecommendationOption(BaseModel):
    option_type: Literal["shared_ground", "cultural_bridge", "stretch_choice", "alternative"]
    title: str
    candidate: Candidate
    explanation: str
    evidence_labels: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    run_id: str
    demo_mode: bool
    location: str
    options: list[RecommendationOption]
    warnings: list[str] = Field(default_factory=list)
    unresolved_interests: list[str] = Field(default_factory=list)
    status: Literal["complete", "partial", "failed"] = "complete"


# --- Group plan lifecycle ---------------------------------------------------------------


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: str = Field(min_length=2, max_length=160)
    budget_per_person: float | None = Field(default=None, gt=0, le=100000)

    @field_validator("location")
    @classmethod
    def clean_location(cls, value: str) -> str:
        return _clean_text(value)


class PlanCreatedResponse(BaseModel):
    plan_id: str
    share_token: str
    expires_at: datetime


class JoinPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=60)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_text(value)


class JoinPlanResponse(BaseModel):
    participant_id: str
    participant_token: str


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interests: list[str] = Field(min_length=1, max_length=3)
    dislikes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("interests", "dislikes")
    @classmethod
    def clean_terms(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return _clean_terms(values, info)


class ParticipantView(BaseModel):
    participant_id: str
    display_name: str
    interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    has_preferences: bool = False


class PlanView(BaseModel):
    plan_id: str
    location: str
    budget_per_person: float | None
    status: str
    expires_at: datetime
    max_participants: int
    participants: list[ParticipantView]
    latest_recommendation: RecommendationResponse | None = None
