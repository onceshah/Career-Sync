"""
Domain models and exceptions for the Google Calendar HITL integration (D8).
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CalendarEventType(str, Enum):
    """Calendar event categories derived from ATS lifecycle states."""

    INTERVIEW = "INTERVIEW"
    ASSESSMENT_DEADLINE = "ASSESSMENT_DEADLINE"
    OFFER_DEADLINE = "OFFER_DEADLINE"
    FOLLOW_UP = "FOLLOW_UP"


class ProposalStatus(str, Enum):
    """Lifecycle of a calendar event proposal awaiting / passing human approval."""

    PENDING = "PENDING"
    CREATED = "CREATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CalendarEventProposal(BaseModel):
    """
    A proposed calendar event derived from an application, staged for HITL approval.

    Proposals are persisted before any external write occurs. A provider event is
    only created when a human explicitly approves the proposal.
    """

    id: str = Field(default_factory=lambda: f"cal-{uuid.uuid4().hex[:12]}")
    application_id: str
    event_type: CalendarEventType
    title: str
    description: str = ""
    start_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=1))
    end_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=1, minutes=45))
    status: ProposalStatus = ProposalStatus.PENDING
    provider: Optional[str] = None
    provider_event_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    note: str = ""


class CalendarError(Exception):
    """Base class for calendar integration failures."""


class CalendarProviderError(CalendarError):
    """Raised when an external calendar provider cannot create an event."""


class ProposalStateError(CalendarError):
    """Raised when a proposal is acted on in an invalid state (e.g. re-approving a rejection)."""
