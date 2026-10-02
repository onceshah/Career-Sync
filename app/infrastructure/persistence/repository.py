"""
SQLAlchemy repository layer for ATS Domain persistence and idempotency tracking (D5).

Transaction model
-----------------
Write operations stage objects on the session but do NOT commit individually.
Driving code that performs multiple related writes must wrap them in
``with repo.transaction():`` so the whole mutation (application, audit
transition, idempotency ledger) commits atomically — or rolls back together.
This removes the partial-state hazard that existed when each method committed
independently.
"""

from contextlib import contextmanager
from typing import Iterator, List, Optional

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Application, Opportunity, StateTransitionRecord
from app.infrastructure.persistence.orm_models import (
    ApplicationORM,
    OpportunityORM,
    ProcessedMessageORM,
    StateTransitionORM,
)


class ATSRepository:
    """
    Repository orchestrating SQLite persistence for Opportunities, Applications, and Audit logs.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Transaction boundary
    # -------------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator["ATSRepository"]:
        """Atomic unit-of-work: commits on success, rolls back on failure."""
        try:
            yield self
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def commit(self) -> None:
        """Explicitly commits the current transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Discards the current transaction. Safe to call even after an exception."""
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Idempotency Ledger
    # -------------------------------------------------------------------------

    def is_message_processed(self, message_id: str) -> bool:
        """Checks if a Gmail message_id has already been processed."""
        record = self.db.query(ProcessedMessageORM).filter(ProcessedMessageORM.message_id == message_id).first()
        return record is not None

    def mark_message_processed(
        self, message_id: str, payload_hash: Optional[str] = None, status: str = "PROCESSED"
    ) -> None:
        """
        Atomically records a message_id in the idempotency ledger.

        Uses SQLite ``INSERT ... ON CONFLICT DO NOTHING`` on the primary key so
        concurrent workers can never double-insert, and re-processing the same
        message never overwrites the original status.
        """
        stmt = (
            sqlite_insert(ProcessedMessageORM)
            .values(message_id=message_id, payload_hash=payload_hash, status=status)
            .on_conflict_do_nothing(index_elements=[ProcessedMessageORM.message_id])
        )
        self.db.execute(stmt)

    # -------------------------------------------------------------------------
    # Opportunities
    # -------------------------------------------------------------------------

    def create_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """Saves a new job opportunity lead."""
        orm_obj = OpportunityORM(
            id=opportunity.id,
            company_name=opportunity.company_name,
            job_title=opportunity.job_title,
            platform=opportunity.platform,
            source_email_id=opportunity.source_email_id,
            discovered_at=opportunity.discovered_at,
            is_promoted=opportunity.is_promoted,
        )
        self.db.add(orm_obj)
        return opportunity

    def find_opportunity(self, company_name: str, job_title: str) -> Optional[Opportunity]:
        """Finds an existing opportunity for a company + role (get-or-create support)."""
        r = (
            self.db.query(OpportunityORM)
            .filter(OpportunityORM.company_name == company_name, OpportunityORM.job_title == job_title)
            .first()
        )
        if not r:
            return None
        return Opportunity(
            id=r.id,
            company_name=r.company_name,
            job_title=r.job_title,
            platform=r.platform,
            source_email_id=r.source_email_id,
            discovered_at=r.discovered_at,
            is_promoted=r.is_promoted,
        )

    def list_opportunities(self) -> List[Opportunity]:
        """Lists all recorded opportunities."""
        records = self.db.query(OpportunityORM).all()
        return [_to_opportunity(r) for r in records]

    # -------------------------------------------------------------------------
    # Applications
    # -------------------------------------------------------------------------

    def create_application(self, application: Application) -> Application:
        """Stages a new Application entity (caller must commit via transaction())."""
        orm_obj = ApplicationORM(
            id=application.id,
            opportunity_id=application.opportunity_id,
            company_name=application.company_name,
            job_title=application.job_title,
            platform=application.platform,
            application_ref_id=application.application_ref_id,
            current_state=application.current_state.value,
            review_status=application.review_status.value,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )
        self.db.add(orm_obj)
        return application

    def get_application_by_id(self, application_id: str) -> Optional[Application]:
        """Fetches an Application by its ID."""
        r = self.db.query(ApplicationORM).filter(ApplicationORM.id == application_id).first()
        return _to_application(r) if r else None

    def list_active_applications(self) -> List[Application]:
        """
        Lists candidate applications for further state updates.

        An application leaves the active matching pool only after a human
        resolves the review that closed it (terminal state + RESOLVED). Terminal
        applications that are still CONFIRMED or NEEDS_REVIEW remain candidates,
        so a contradictory follow-up (e.g. an invite after a rejection) resolves
        to the SAME entity and routes to NEEDS_REVIEW instead of silently
        creating a duplicate application.
        """
        terminal_states = (
            ApplicationLifecycleState.REJECTED.value,
            ApplicationLifecycleState.WITHDRAWN.value,
            ApplicationLifecycleState.EXPIRED.value,
        )
        records = (
            self.db.query(ApplicationORM)
            .filter(
                (ApplicationORM.current_state.notin_(terminal_states))
                | (ApplicationORM.review_status != ReviewStatus.RESOLVED.value)
            )
            .order_by(ApplicationORM.updated_at.desc())
            .all()
        )
        return [_to_application(r) for r in records]

    def list_needs_review(self) -> List[Application]:
        """Lists applications currently flagged for human review (HITL queue)."""
        records = (
            self.db.query(ApplicationORM)
            .filter(ApplicationORM.review_status == ReviewStatus.NEEDS_REVIEW.value)
            .order_by(ApplicationORM.updated_at.desc())
            .all()
        )
        return [_to_application(r) for r in records]

    def update_application_state(
        self, application_id: str, new_state: ApplicationLifecycleState, review_status: ReviewStatus = ReviewStatus.CONFIRMED
    ) -> Optional[Application]:
        """Stages a state + review-status update for an Application."""
        r = self.db.query(ApplicationORM).filter(ApplicationORM.id == application_id).first()
        if not r:
            return None
        r.current_state = new_state.value
        r.review_status = review_status.value
        return _to_application(r)

    def resolve_review(
        self, application_id: str, confirmed_state: ApplicationLifecycleState
    ) -> Optional[Application]:
        """
        Human-in-the-loop approval: applies the verified state to a NEEDS_REVIEW
        application and marks the review RESOLVED.
        """
        r = self.db.query(ApplicationORM).filter(ApplicationORM.id == application_id).first()
        if not r:
            return None
        r.current_state = confirmed_state.value
        r.review_status = ReviewStatus.RESOLVED.value
        return _to_application(r)

    # -------------------------------------------------------------------------
    # State Transitions Audit History
    # -------------------------------------------------------------------------

    def record_transition(self, record: StateTransitionRecord) -> StateTransitionRecord:
        """Stages an immutable state transition in the audit history (caller commits)."""
        orm_obj = StateTransitionORM(
            id=record.id,
            application_id=record.application_id,
            previous_state=record.previous_state.value,
            new_state=record.new_state.value,
            triggering_message_id=record.triggering_message_id,
            evidence_snippet=record.evidence.snippet if record.evidence else None,
            review_status=record.review_status.value,
            reasoning=record.reasoning,
            timestamp=record.timestamp,
        )
        self.db.add(orm_obj)
        return record

    def list_transitions(self, application_id: str) -> List[StateTransitionRecord]:
        """Lists the full audit trail for an Application (oldest first)."""
        records = (
            self.db.query(StateTransitionORM)
            .filter(StateTransitionORM.application_id == application_id)
            .order_by(StateTransitionORM.timestamp.asc())
            .all()
        )
        return [
            StateTransitionRecord(
                id=r.id,
                application_id=r.application_id,
                previous_state=ApplicationLifecycleState(r.previous_state),
                new_state=ApplicationLifecycleState(r.new_state),
                triggering_message_id=r.triggering_message_id,
                evidence=_evidence_from_snippet(r.evidence_snippet, r.triggering_message_id),
                review_status=ReviewStatus(r.review_status),
                reasoning=r.reasoning or "",
                timestamp=r.timestamp,
            )
            for r in records
        ]


# ---------------------------------------------------------------------------
# Mapping helpers (ORM -> Domain)
# ---------------------------------------------------------------------------

def _to_opportunity(r: OpportunityORM) -> Opportunity:
    return Opportunity(
        id=r.id,
        company_name=r.company_name,
        job_title=r.job_title,
        platform=r.platform,
        source_email_id=r.source_email_id,
        discovered_at=r.discovered_at,
        is_promoted=r.is_promoted,
    )


def _to_application(r: ApplicationORM) -> Application:
    return Application(
        id=r.id,
        opportunity_id=r.opportunity_id,
        company_name=r.company_name,
        job_title=r.job_title,
        platform=r.platform,
        application_ref_id=r.application_ref_id,
        current_state=ApplicationLifecycleState(r.current_state),
        review_status=ReviewStatus(r.review_status),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _evidence_from_snippet(snippet: Optional[str], message_id: str):
    from app.domain.ats_models import ExtractedEvidence

    return ExtractedEvidence(source_message_id=message_id, snippet=snippet or "")