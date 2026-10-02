"""
SQLAlchemy 2.0 ORM schema definitions for CareerSync (D5).

Integrity guarantees added (relative to the original schema):
  - Unique `application_ref_id` (nullable) so Tier-1 entity matching is stable.
  - Unique `(application_id, triggering_message_id)` on transitions so a single
    Gmail message can never replay the same audit transition.
  - CHECK constraints bind `current_state`, `review_status` and `status` values
    to the ATS enums, preventing invalid states from ever hitting the DB.
  - `ondelete="CASCADE"` so deleting an application removes its audit trail.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.database import Base

ATS_STATES = (
    "DISCOVERED", "INTERESTED", "APPLIED", "ASSESSMENT",
    "INTERVIEW", "OFFER_SELECTED", "REJECTED", "WITHDRAWN", "EXPIRED",
)
REVIEW_STATUSES = ("CONFIRMED", "NEEDS_REVIEW", "RESOLVED")
CALENDAR_EVENT_TYPES = ("INTERVIEW", "ASSESSMENT_DEADLINE", "OFFER_DEADLINE", "FOLLOW_UP")
PROPOSAL_STATUSES = ("PENDING", "CREATED", "REJECTED", "FAILED")


class OpportunityORM(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("company_name", "job_title", name="uq_opportunity_company_role"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    source_email_id: Mapped[str] = mapped_column(String, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False)

    applications: Mapped[list["ApplicationORM"]] = relationship(back_populates="opportunity")


class ApplicationORM(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("application_ref_id", name="uq_application_ref_id"),
        CheckConstraint("current_state IN %s" % repr(tuple(ATS_STATES)), name="ck_application_current_state"),
        CheckConstraint("review_status IN %s" % repr(tuple(REVIEW_STATUSES)), name="ck_application_review_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    application_ref_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    current_state: Mapped[str] = mapped_column(String, nullable=False, default="APPLIED")
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="CONFIRMED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    opportunity: Mapped["OpportunityORM | None"] = relationship(back_populates="applications")
    transitions: Mapped[list["StateTransitionORM"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", passive_deletes=True
    )


class StateTransitionORM(Base):
    __tablename__ = "state_transitions"
    __table_args__ = (
        UniqueConstraint("application_id", "triggering_message_id", name="uq_transition_message"),
        CheckConstraint("review_status IN %s" % repr(tuple(REVIEW_STATUSES)), name="ck_transition_review_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_state: Mapped[str] = mapped_column(String, nullable=False)
    new_state: Mapped[str] = mapped_column(String, nullable=False)
    triggering_message_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    evidence_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="CONFIRMED")
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    application: Mapped["ApplicationORM"] = relationship(back_populates="transitions")


class ProcessedMessageORM(Base):
    __tablename__ = "processed_messages"
    __table_args__ = (
        CheckConstraint("status IN ('PROCESSED','ARCHIVED_NON_CAREER','OPPORTUNITY_DISCOVERED','APPLICATION_CREATED','APPLICATION_UPDATED','NEEDS_REVIEW_STAGED')", name="ck_processed_status"),
    )

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PROCESSED")
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class CalendarEventProposalORM(Base):
    """
    Persisted calendar event proposal awaiting / passing human-in-the-loop approval (D8).

    ``status`` and ``event_type`` are CHECK-bound to their enums so an invalid
    proposal state can never be persisted.
    """

    __tablename__ = "calendar_event_proposals"
    __table_args__ = (
        CheckConstraint("event_type IN %s" % repr(tuple(CALENDAR_EVENT_TYPES)), name="ck_calendar_event_type"),
        CheckConstraint("status IN %s" % repr(tuple(PROPOSAL_STATUSES)), name="ck_calendar_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING", index=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)