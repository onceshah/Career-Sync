"""
Repository for persisted calendar event proposals (D8).

Mirrors the transaction model of :class:`ATSRepository`: writes stage objects on
the session and callers wrap related mutations in ``with repo.transaction():``.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from sqlalchemy.orm import Session

from app.calendar.models import CalendarEventProposal, CalendarEventType, ProposalStatus
from app.infrastructure.persistence.orm_models import CalendarEventProposalORM


class CalendarRepository:
    """Persistence for calendar event proposals (HITL staging queue)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @contextmanager
    def transaction(self) -> Iterator["CalendarRepository"]:
        try:
            yield self
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def create_proposal(self, proposal: CalendarEventProposal) -> CalendarEventProposal:
        self.db.add(_to_orm(proposal))
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[CalendarEventProposal]:
        record = (
            self.db.query(CalendarEventProposalORM)
            .filter(CalendarEventProposalORM.id == proposal_id)
            .first()
        )
        return _to_domain(record) if record else None

    def list_proposals(self, status: Optional[ProposalStatus] = None) -> List[CalendarEventProposal]:
        query = self.db.query(CalendarEventProposalORM)
        if status is not None:
            query = query.filter(CalendarEventProposalORM.status == status.value)
        records = query.order_by(CalendarEventProposalORM.created_at.desc()).all()
        return [_to_domain(r) for r in records]

    def update_proposal_status(
        self,
        proposal_id: str,
        status: ProposalStatus,
        provider: Optional[str] = None,
        provider_event_id: Optional[str] = None,
        note: str = "",
    ) -> Optional[CalendarEventProposal]:
        record = (
            self.db.query(CalendarEventProposalORM)
            .filter(CalendarEventProposalORM.id == proposal_id)
            .first()
        )
        if not record:
            return None
        record.status = status.value
        record.provider = provider
        record.provider_event_id = provider_event_id
        record.note = note
        record.decided_at = datetime.now(timezone.utc)
        return _to_domain(record)


def _to_orm(proposal: CalendarEventProposal) -> CalendarEventProposalORM:
    return CalendarEventProposalORM(
        id=proposal.id,
        application_id=proposal.application_id,
        event_type=proposal.event_type.value,
        title=proposal.title,
        description=proposal.description,
        start_at=proposal.start_at,
        end_at=proposal.end_at,
        status=proposal.status.value,
        provider=proposal.provider,
        provider_event_id=proposal.provider_event_id,
        note=proposal.note,
        created_at=proposal.created_at,
        decided_at=proposal.decided_at,
    )


def _to_domain(record: CalendarEventProposalORM) -> CalendarEventProposal:
    return CalendarEventProposal(
        id=record.id,
        application_id=record.application_id,
        event_type=CalendarEventType(record.event_type),
        title=record.title,
        description=record.description or "",
        start_at=record.start_at,
        end_at=record.end_at,
        status=ProposalStatus(record.status),
        provider=record.provider,
        provider_event_id=record.provider_event_id,
        note=record.note or "",
        created_at=record.created_at,
        decided_at=record.decided_at,
    )
