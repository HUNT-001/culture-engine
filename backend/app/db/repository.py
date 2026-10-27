"""Persistence boundary for anonymous, expiring group plans."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.security import hash_token, new_token, token_matches
from app.db.models import ParticipantModel, PlanModel, PreferenceModel, RecommendationRunModel
from app.domain.currency import DEFAULT_CURRENCY
from app.services.resolution import confirmed_index, normalize_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_expired(plan: PlanModel, now: datetime | None = None) -> bool:
    return as_utc(plan.expires_at) <= (now or utc_now())


def purge_expired_plans(db: Session, now: datetime | None = None, limit: int = 100) -> int:
    """Delete expired plans with their participants, preferences and runs (bounded per call)."""
    now = now or utc_now()
    expired = db.scalars(select(PlanModel).where(PlanModel.expires_at <= now).limit(limit)).all()
    if not expired:
        return 0
    ids = [plan.id for plan in expired]
    # Runs hold participant names/interests, so they expire with the plan.
    db.execute(delete(RecommendationRunModel).where(RecommendationRunModel.plan_id.in_(ids)))
    for plan in expired:
        db.delete(plan)
    db.commit()
    return len(ids)


def create_plan(
    db: Session, location: str, budget_per_person: float | None, ttl_hours: int,
    budget_currency: str = DEFAULT_CURRENCY,
) -> tuple[PlanModel, str]:
    token = new_token()
    plan = PlanModel(
        location=location,
        budget_per_person=budget_per_person,
        budget_currency=budget_currency,
        share_token_hash=hash_token(token),
        expires_at=utc_now() + timedelta(hours=ttl_hours),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan, token


def get_plan_for_share_token(
    db: Session, plan_id: str, share_token: str | None, lock: bool = False
) -> PlanModel | None:
    query = select(PlanModel).where(PlanModel.id == plan_id)
    if lock:
        query = query.with_for_update()
    plan = db.scalars(query).first()
    if plan is None or not token_matches(share_token, plan.share_token_hash):
        return None
    return plan


def add_participant(db: Session, plan: PlanModel, display_name: str) -> tuple[ParticipantModel, str]:
    token = new_token()
    participant = ParticipantModel(
        id=str(uuid4()), plan_id=plan.id, display_name=display_name, join_token_hash=hash_token(token)
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant, token


def get_participant_for_token(
    db: Session, plan_id: str, participant_id: str, participant_token: str | None
) -> ParticipantModel | None:
    participant = db.scalars(
        select(ParticipantModel).where(
            ParticipantModel.id == participant_id, ParticipantModel.plan_id == plan_id
        )
    ).first()
    if participant is None or not token_matches(participant_token, participant.join_token_hash):
        return None
    return participant


def replace_preferences(
    db: Session,
    participant: ParticipantModel,
    interests: list[str],
    dislikes: list[str],
    resolved: list | None = None,
) -> ParticipantModel:
    """Replace a participant's preferences, persisting any confirmed Qloo entity.

    `resolved` is a confirmed-entity overlay (ResolvedInterestInput-like objects) matched to
    interest text; its entity_id / verified name are stored so interests are not re-resolved.
    """
    index = confirmed_index(resolved or [])
    participant.preferences.clear()
    for term in interests:
        match = index.get(normalize_name(term))
        participant.preferences.append(PreferenceModel(
            display_name=term,
            kind="interest",
            entity_id=match["entity_id"] if match else None,
            entity_type=(match.get("entity_type") if match else None),
            resolved_name=match["name"] if match else None,
        ))
    for term in dislikes:
        participant.preferences.append(PreferenceModel(display_name=term, kind="dislike"))
    db.commit()
    db.refresh(participant)
    return participant


def save_run(db: Session, plan: PlanModel, run_id: str, result: dict, status: str) -> RecommendationRunModel:
    run = RecommendationRunModel(id=run_id, plan_id=plan.id, status=status, result_json=result)
    db.add(run)
    if status != "failed":
        # A run that produced nothing (e.g. no interest confirmed) is kept for display but
        # must not mark the plan as recommended.
        plan.status = "recommended"
    db.commit()
    return run


def latest_run(db: Session, plan_id: str) -> RecommendationRunModel | None:
    return db.scalars(
        select(RecommendationRunModel)
        .where(RecommendationRunModel.plan_id == plan_id)
        .order_by(RecommendationRunModel.created_at.desc())
        .limit(1)
    ).first()
