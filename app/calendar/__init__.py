"""
Google Calendar integration + human-in-the-loop (HITL) approval package (D8).

Pipeline position:
    CareerSyncEngine (ATS state)  ->  CalendarService.propose()   (PENDING)
    Student approves in UI/API    ->  CalendarService.approve()   (provider event)

The provider is swappable: ``InMemoryCalendarProvider`` for local/dev/test runs
and ``GoogleCalendarProvider`` for real Google Calendar writes. Nothing is ever
written to a real calendar without an explicit human approval step.
"""

from app.calendar.interfaces import CalendarProvider
from app.calendar.models import CalendarEventProposal, CalendarEventType, ProposalStatus
from app.calendar.service import CalendarService

__all__ = [
    "CalendarProvider",
    "CalendarService",
    "CalendarEventProposal",
    "CalendarEventType",
    "ProposalStatus",
]
