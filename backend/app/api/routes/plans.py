"""Anonymous, expiring group plans: create, join via share token, set preferences, run, retrieve.

Tokens travel in headers (not URLs, which end up in logs). Unknown plans and invalid tokens
both return 404 so the API does not reveal which plan IDs exist.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.routes.recommendations import execute_workflow
from app.core.config import Settings, get_settings
from app.db import repository as repo
from app.db.models import ParticipantModel, PlanModel
from app.db.session import get_db
from app.domain.currency import DEFAULT_CURRENCY
from app.domain.schemas import (
    JoinPlanRequest,
    JoinPlanResponse,
    ParticipantInput,
    ParticipantView,
    PlanCreatedResponse,
    PlanCreateRequest,
    PlanView,
    PreferencesUpdate,
    RecommendationRequest,
    RecommendationResponse,
    ResolvedInterestInput,
    ResolvedInterestView,
)
from app.services.runtime import get_runtime

router = APIRouter(prefix="/plans", tags=["plans"])

NOT_FOUND = "Plan not found or the link is invalid."


def _require_token(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token.")
    return token


def _load_plan(db: Session, plan_id: str, share_token: str | None, lock: bool = False) -> PlanModel:
    plan = repo.get_plan_for_share_token(db, plan_id, _require_token(share_token), lock=lock)
    if plan is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if repo.is_expired(plan):
        raise HTTPException(status_code=410, detail="This plan has expired.")
    return plan


def _participant_view(participant: ParticipantModel) -> ParticipantView:
    interest_prefs = [p for p in participant.preferences if p.kind == "interest"]
    interests = [p.display_name for p in interest_prefs]
    dislikes = [p.display_name for p in participant.preferences if p.kind == "dislike"]
    resolved = [
        ResolvedInterestView(
            text=p.display_name,
            entity_id=p.entity_id,
            name=p.resolved_name or p.display_name,
            entity_type=p.entity_type or "unknown",
        )
        for p in interest_prefs
        if p.entity_id
    ]
    return ParticipantView(
        participant_id=participant.id,
        display_name=participant.display_name,
        interests=interests,
        resolved_interests=resolved,
        dislikes=dislikes,
        has_preferences=bool(interests),
    )


@router.post("", status_code=201, response_model=PlanCreatedResponse)
def create_plan(
    body: PlanCreateRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    repo.purge_expired_plans(db)
    plan, token = repo.create_plan(
        db, body.location, body.budget_per_person, settings.plan_ttl_hours, body.budget_currency
    )
    return PlanCreatedResponse(plan_id=plan.id, share_token=token, expires_at=repo.as_utc(plan.expires_at))


@router.get("/{plan_id}", response_model=PlanView)
def get_plan(
    plan_id: str,
    x_share_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    plan = _load_plan(db, plan_id, x_share_token)
    run = repo.latest_run(db, plan.id)
    return PlanView(
        plan_id=plan.id,
        location=plan.location,
        budget_per_person=plan.budget_per_person,
        budget_currency=plan.budget_currency or DEFAULT_CURRENCY,
        status=plan.status,
        expires_at=repo.as_utc(plan.expires_at),
        max_participants=settings.max_participants,
        participants=[_participant_view(p) for p in plan.participants],
        latest_recommendation=RecommendationResponse.model_validate(run.result_json) if run else None,
    )


@router.post("/{plan_id}/participants", status_code=201, response_model=JoinPlanResponse)
def join_plan(
    plan_id: str,
    body: JoinPlanRequest,
    x_share_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    plan = _load_plan(db, plan_id, x_share_token, lock=True)
    if len(plan.participants) >= settings.max_participants:
        raise HTTPException(status_code=409, detail=f"This plan already has {settings.max_participants} participants.")
    participant, token = repo.add_participant(db, plan, body.display_name)
    return JoinPlanResponse(participant_id=participant.id, participant_token=token)


@router.put("/{plan_id}/participants/{participant_id}/preferences", response_model=ParticipantView)
def update_preferences(
    plan_id: str,
    participant_id: str,
    body: PreferencesUpdate,
    x_participant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    participant = repo.get_participant_for_token(
        db, plan_id, participant_id, _require_token(x_participant_token)
    )
    if participant is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if repo.is_expired(participant.plan):
        raise HTTPException(status_code=410, detail="This plan has expired.")
    participant = repo.replace_preferences(
        db, participant, body.interests, body.dislikes, resolved=body.resolved_interests
    )
    return _participant_view(participant)


@router.post("/{plan_id}/recommendations", response_model=RecommendationResponse)
async def run_plan_recommendations(
    plan_id: str,
    x_share_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    runtime: dict = Depends(get_runtime),
):
    # Synchronous DB work runs in the threadpool so it does not block the event loop.
    plan = await run_in_threadpool(_load_plan, db, plan_id, x_share_token)
    views = await run_in_threadpool(lambda: [_participant_view(p) for p in plan.participants])
    ready = [v for v in views if v.has_preferences]
    if len(ready) < 2:
        raise HTTPException(
            status_code=409, detail="At least two participants need to add interests before recommendations."
        )
    request = RecommendationRequest(
        location=plan.location,
        budget_per_person=plan.budget_per_person,
        budget_currency=plan.budget_currency or DEFAULT_CURRENCY,
        participants=[
            ParticipantInput(
                participant_id=v.participant_id,
                display_name=v.display_name,
                interests=v.interests,
                # Confirmed entities persisted earlier flow straight to Insights — the
                # workflow does not re-resolve them.
                resolved_interests=[
                    ResolvedInterestInput(
                        text=r.text, entity_id=r.entity_id, name=r.name, entity_type=r.entity_type
                    )
                    for r in v.resolved_interests
                ],
                dislikes=v.dislikes,
            )
            for v in ready
        ],
    )
    response = await execute_workflow(runtime, request)
    if len(ready) < len(views):
        response.warnings.append("Participants who have not added interests yet were not included.")
    await run_in_threadpool(
        repo.save_run, db, plan, response.run_id, response.model_dump(mode="json"), response.status
    )
    return response
