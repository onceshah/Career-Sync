"""
In-memory calendar provider used for local development, demos and tests.

Records created events in a dictionary so the approval workflow can be exercised
end-to-end without any Google OAuth credentials.
"""

import uuid

from app.calendar.interfaces import CalendarProvider
from app.calendar.models import CalendarEventProposal


class InMemoryCalendarProvider(CalendarProvider):
    """Non-persistent calendar provider that records events in memory."""

    provider_name = "memory"

    def __init__(self) -> None:
        self.events: dict[str, CalendarEventProposal] = {}

    def create_event(self, proposal: CalendarEventProposal) -> str:
        event_id = f"mem-{uuid.uuid4().hex[:12]}"
        self.events[event_id] = proposal.model_copy(deep=True)
        return event_id
