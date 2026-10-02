"""
CalendarService: derives calendar event proposals from ATS applications and
executes the human-in-the-loop approval workflow (D8).

Safety invariant
----------------
``propose`` never touches an external calendar. A provider event is created only
inside ``approve``, which is reachable solely through an explicit human action
(API call / dashboard button). Rejections and failures are recorded on the
proposal, and failed provider writes never mutate the ATS application state.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.calendar.interfaces import CalendarProvider
from app.calendar.models import (
    CalendarEventProposal,
    CalendarEventType,
    CalendarProviderError,
    ProposalStateError,
    ProposalStatus,
)
from app.domain.ats_enums import ApplicationLifecycleState
from app.domain.ats_models import Application
from app.infrastructure.persistence.calendar_repository import CalendarRepository

logger = logging.getLogger(__name__)

DEFAULT_DURATION_MINUTES = 45

# Lifecycle state -> the calendar event it naturally implies.
STATE_TO_EVENT_TYPE = {
    ApplicationLifecycleState.INTERVIEW: CalendarEventType.INTERVIEW,
    ApplicationLifecycleState.ASSESSMENT: CalendarEventType.ASSESSMENT_DEADLINE,
    ApplicationLifecycleState.OFFER_SELECTED: CalendarEventType.OFFER_DEADLINE,
}

EVENT_TYPE_LABELS = {
    CalendarEventType.INTERVIEW: "Interview",
    CalendarEventType.ASSESSMENT_DEADLINE: "Assessment Deadline",
    CalendarEventType.OFFER_DEADLINE: "Offer Deadline",
    CalendarEventType.FOLLOW_UP: "Follow-up",
}


class CalendarService:
    """Proposes, lists, approves and rejects calendar events for applications."""

    def __init__(self, repository: CalendarRepository, provider: CalendarProvider) -> None:
        self.repository = repository
        self.provider = provider

    # ------------------------------------------------------------------
    # Proposal creation (HITL staging)
    # ------------------------------------------------------------------

    def propose(
        self,
        application: Application,
        event_type: Optional[CalendarEventType] = None,
        start_at: Optional[datetime] = None,
        duration_minutes: int = DEFAULT_DURATION_MINUTES,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CalendarEventProposal:
        """
        Stages a calendar event proposal for an application without writing to any
        external calendar. The proposal is PENDING until a human approves it.
        """
        resolved_type = (
            event_type
            or STATE_TO_EVENT_TYPE.get(application.current_state)
            or CalendarEventType.FOLLOW_UP
        )
        start = start_at or (datetime.now(timezone.utc) + timedelta(days=1))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=max(5, duration_minutes))

        label = EVENT_TYPE_LABELS[resolved_type]
        proposal = CalendarEventProposal(
            application_id=application.id,
            event_type=resolved_type,
            title=title or f"{label}: {application.job_title} at {application.company_name}",
            description=description
            or (
                f"{label} for the {application.job_title} role at "
                f"{application.company_name} (application {application.id})."
            ),
            start_at=start,
            end_at=end,
        )
        with self.repository.transaction():
            self.repository.create_proposal(proposal)
        logger.info(
            "Staged %s calendar proposal '%s' for application '%s'.",
            resolved_type.value,
            proposal.id,
            application.id,
        )
        return proposal

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_proposals(self, status: Optional[ProposalStatus] = None) -> List[CalendarEventProposal]:
        return self.repository.list_proposals(status=status)

    def get_proposal(self, proposal_id: str) -> Optional[CalendarEventProposal]:
        return self.repository.get_proposal(proposal_id)

    # ------------------------------------------------------------------
    # HITL decisions
    # ------------------------------------------------------------------

    def approve(self, proposal_id: str) -> CalendarEventProposal:
        """
        Human approval: creates the external calendar event for a PENDING proposal.

        On provider failure the proposal is marked FAILED and the error is
        re-raised so the caller can surface it; no ATS state is affected.
        """
        proposal = self.repository.get_proposal(proposal_id)
        if proposal is None:
            raise ProposalStateError(f"Calendar proposal '{proposal_id}' not found.")
        if proposal.status == ProposalStatus.CREATED:
            return proposal
        if proposal.status != ProposalStatus.PENDING:
            raise ProposalStateError(
                f"Calendar proposal '{proposal_id}' cannot be approved from status "
                f"{proposal.status.value}."
            )

        try:
            event_id = self.provider.create_event(proposal)
        except CalendarProviderError as exc:
            with self.repository.transaction():
                self.repository.update_proposal_status(
                    proposal_id, ProposalStatus.FAILED, note=str(exc)
                )
            logger.error("Calendar provider failed for proposal '%s': %s", proposal_id, exc)
            raise

        with self.repository.transaction():
            updated = self.repository.update_proposal_status(
                proposal_id,
                ProposalStatus.CREATED,
                provider=self.provider.provider_name,
                provider_event_id=event_id,
            )
        logger.info(
            "Approved calendar proposal '%s' -> %s event '%s'.",
            proposal_id,
            self.provider.provider_name,
            event_id,
        )
        return updated

    def reject(self, proposal_id: str, note: str = "") -> CalendarEventProposal:
        """Human rejection: discards a PENDING proposal without touching the provider."""
        proposal = self.repository.get_proposal(proposal_id)
        if proposal is None:
            raise ProposalStateError(f"Calendar proposal '{proposal_id}' not found.")
        if proposal.status != ProposalStatus.PENDING:
            raise ProposalStateError(
                f"Calendar proposal '{proposal_id}' cannot be rejected from status "
                f"{proposal.status.value}."
            )
        with self.repository.transaction():
            updated = self.repository.update_proposal_status(
                proposal_id, ProposalStatus.REJECTED, note=note
            )
        logger.info("Rejected calendar proposal '%s'.", proposal_id)
        return updated
