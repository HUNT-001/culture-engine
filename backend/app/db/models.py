from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.domain.currency import DEFAULT_CURRENCY


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlanModel(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    # SHA-256 of the share token; the raw token is returned once at creation and never stored.
    share_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    budget_per_person: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ISO 4217 code for budget_per_person. Plans that predate this column read as INR.
    budget_currency: Mapped[str] = mapped_column(
        String(3), default=DEFAULT_CURRENCY, server_default=DEFAULT_CURRENCY, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="created", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    participants: Mapped[list["ParticipantModel"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="ParticipantModel.created_at"
    )


class ParticipantModel(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    join_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    plan: Mapped[PlanModel] = relationship(back_populates="participants")
    preferences: Mapped[list["PreferenceModel"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan", order_by="PreferenceModel.id"
    )


class PreferenceModel(Base):
    __tablename__ = "preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    # The original text the user typed for this interest/dislike.
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Confirmed Qloo entity, when the user selected one (null = unconfirmed/unresolved).
    entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Verified Qloo display name for the confirmed entity (null when unconfirmed).
    resolved_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="interest", nullable=False)
    participant: Mapped[ParticipantModel] = relationship(back_populates="preferences")


class RecommendationRunModel(Base):
    __tablename__ = "recommendation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="started", nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warning_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
