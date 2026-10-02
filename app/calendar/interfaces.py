"""
Provider abstraction for the calendar integration (D8).
"""

from abc import ABC, abstractmethod

from app.calendar.models import CalendarEventProposal


class CalendarProvider(ABC):
    """
    Abstract calendar provider.

    Implementations translate an approved :class:`CalendarEventProposal` into a
    concrete external event and return the provider's event identifier.
    """

    provider_name: str = "unknown"

    @abstractmethod
    def create_event(self, proposal: CalendarEventProposal) -> str:
        """
        Creates the external calendar event for an approved proposal.

        Returns:
            The provider-assigned event identifier.

        Raises:
            CalendarProviderError: If the event cannot be created.
        """
        raise NotImplementedError
