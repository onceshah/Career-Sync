"""
Pydantic domain models for Opportunity, Application, and StateTransition entities (D5).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus


class ExtractedEvidence(BaseModel):
    """
    Evidence extracted from an email payload triggering an ATS state proposal.
    """
    source_message_id: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    platform: Optional[str] = None
    application_id: Optional[str] = None
    deadline: Optional[str] = None
    snippet: str = ""


class Opportunity(BaseModel):
    """
    Represents a discovered job lead or campus opportunity.
    An Opportunity is a lead only and does NOT automatically represent an active Application.
    """
    id: str = Field(default_factory=lambda: f"opp-{uuid.uuid4().hex[:12]}")
    company_name: str
    job_title: str
    platform: Optional[str] = "Unknown"
    source_email_id: str
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_promoted: bool = False


class Application(BaseModel):
    """
    Represents an active job application submitted by the student.
    Tracks ongoing state across multiple incoming email updates.
    """
    id: str = Field(default_factory=lambda: f"app-{uuid.uuid4().hex[:12]}")
    opportunity_id: Optional[str] = None
    company_name: str
    job_title: str
    platform: Optional[str] = "Unknown"
    application_ref_id: Optional[str] = None
    current_state: ApplicationLifecycleState = ApplicationLifecycleState.APPLIED
    review_status: ReviewStatus = ReviewStatus.CONFIRMED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StateTransitionRecord(BaseModel):
    """
    Immutable historical audit record of an ATS lifecycle state transition.
    """
    id: str = Field(default_factory=lambda: f"txn-{uuid.uuid4().hex[:12]}")
    application_id: str
    previous_state: ApplicationLifecycleState
    new_state: ApplicationLifecycleState
    triggering_message_id: str
    evidence: ExtractedEvidence
    review_status: ReviewStatus = ReviewStatus.CONFIRMED
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
