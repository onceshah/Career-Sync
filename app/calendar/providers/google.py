"""
Google Calendar provider (D8).

Writes an approved proposal to Google Calendar via the Calendar v3 API. The
provider is credential-injected so it stays testable and so no OAuth flow is
triggered implicitly:

    provider = GoogleCalendarProvider(credentials=google_credentials)
    provider.create_event(proposal)
"""

import logging
from typing import Any, Optional

from app.calendar.interfaces import CalendarProvider
from app.calendar.models import CalendarEventProposal, CalendarProviderError

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar v3 provider backed by injected OAuth credentials."""

    provider_name = "google"

    def __init__(self, credentials: Optional[Any] = None, calendar_id: str = "primary") -> None:
        self._credentials = credentials
        self.calendar_id = calendar_id

    def _build_service(self):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - dependency present in prod
            raise CalendarProviderError(
                "google-api-python-client is not installed."
            ) from exc

        if self._credentials is None:
            raise CalendarProviderError(
                "Google Calendar credentials are not configured. "
                "Complete the OAuth flow before approving calendar events."
            )

        return build(
            "calendar",
            "v3",
            credentials=self._credentials,
            cache_discovery=False,
        )

    def create_event(self, proposal: CalendarEventProposal) -> str:
        service = self._build_service()
        body = {
            "summary": proposal.title,
            "description": proposal.description,
            "start": {"dateTime": proposal.start_at.isoformat()},
            "end": {"dateTime": proposal.end_at.isoformat()},
        }
        try:
            created = (
                service.events()
                .insert(calendarId=self.calendar_id, body=body)
                .execute()
            )
        except CalendarProviderError:
            raise
        except Exception as exc:
            logger.exception("Google Calendar event creation failed.")
            raise CalendarProviderError(f"Google Calendar event creation failed: {exc}") from exc

        event_id = created.get("id")
        if not event_id:  # pragma: no cover - defensive
            raise CalendarProviderError("Google Calendar returned no event id.")
        logger.info("Created Google Calendar event '%s' for application '%s'.", event_id, proposal.application_id)
        return event_id
