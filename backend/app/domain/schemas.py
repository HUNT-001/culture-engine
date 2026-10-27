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


class ResolvedInterestInput(BaseModel):
    """A user-confirmed interest: the typed text plus the Qloo entity the user selected.

    When present, the workflow uses this entity directly and does NOT re-resolve the text.
    """
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_TERM_LENGTH)
    entity_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(default="unknown", max_length=100)

    @field_validator("text", "entity_id", "name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return _clean_text(value)


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=60)
    interests: list[str] = Field(min_length=1, max_length=3)
    # Optional confirmed-entity overlay, matched to `interests` by text (case-insensitive).
    resolved_interests: list[ResolvedInterestInput] = Field(default_factory=list, max_length=3)
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
    # Verified interest names that Qloo's explainability credited for this candidate.
    # Populated only from exact entity-id matches to resolved interests — never guessed
    # from a UUID. A Qloo-provided link, distinct from our coverage/ranking calculation.
    matched_interests: list[str] = Field(default_factory=list)
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


class UnconfirmedInterest(BaseModel):
    """An interest that was excluded because the user has not confirmed a Qloo entity for it."""

    participant_id: str
    display_name: str
    text: str


class RecommendationResponse(BaseModel):
    run_id: str
    demo_mode: bool
    location: str
    options: list[RecommendationOption]
    warnings: list[str] = Field(default_factory=list)
    unresolved_interests: list[str] = Field(default_factory=list)
    # Interests excluded for lack of explicit confirmation (never auto-matched by name).
    needs_confirmation: list[UnconfirmedInterest] = Field(default_factory=list)
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
    # Optional confirmed-entity overlay matched to `interests` by text.
    resolved_interests: list[ResolvedInterestInput] = Field(default_factory=list, max_length=3)
    dislikes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("interests", "dislikes")
    @classmethod
    def clean_terms(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return _clean_terms(values, info)


class ResolvedInterestView(BaseModel):
    text: str
    entity_id: str
    name: str
    entity_type: str = "unknown"


class ParticipantView(BaseModel):
    participant_id: str
    display_name: str
    interests: list[str] = Field(default_factory=list)
    # Confirmed entities among the interests, for the UI to restore saved selections.
    resolved_interests: list[ResolvedInterestView] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    has_preferences: bool = False


# --- Entity search (bounded user confirmation) ------------------------------------------


class EntityCandidate(BaseModel):
    entity_id: str
    name: str
    entity_type: str = "unknown"
    disambiguation: str | None = None
    # "qloo" = a real Qloo entity; "mock" = synthetic demo entity, never a real match.
    source: Literal["qloo", "mock"] = "qloo"


class EntitySearchResponse(BaseModel):
    query: str
    demo_mode: bool
    candidates: list[EntityCandidate] = Field(default_factory=list)


class PlanView(BaseModel):
    plan_id: str
    location: str
    budget_per_person: float | None
    status: str
    expires_at: datetime
    max_participants: int
    participants: list[ParticipantView]
    latest_recommendation: RecommendationResponse | None = None
