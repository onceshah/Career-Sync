"""
Gmail API client implementation adhering to EmailProviderClient.

Consumes authenticated UserCredentials via constructor dependency injection.
Does not perform OAuth authentication.
"""

import logging
from datetime import timezone
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError

from app.auth.interfaces import EmailProviderClient
from app.auth.models import UserCredentials
from app.ingestion.config import GmailConfig
from app.ingestion.exceptions import EmailFetchError

logger = logging.getLogger(__name__)


class GmailClient(EmailProviderClient):
    """
    Gmail API client backed by authenticated Google OAuth credentials.
    """

    def __init__(
        self,
        credentials: UserCredentials,
        config: Optional[GmailConfig] = None,
    ):
        self.credentials = credentials
        self.config = config or GmailConfig()
        self.service = None

        self._initialize_google_service()

    @property
    def provider_name(self) -> str:
        return "gmail"

    @property
    def is_authenticated(self) -> bool:
        return self.service is not None

    def _initialize_google_service(self) -> None:
        """
        Creates an authenticated Gmail API service using injected credentials.
        """
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            expires_at = self.credentials.tokens.expires_at

            if (
                expires_at is not None
                and expires_at.tzinfo is not None
            ):
                expires_at = (
                    expires_at
                    .astimezone(timezone.utc)
                    .replace(tzinfo=None)
                )

            google_credentials = Credentials(
                token=self.credentials.tokens.access_token,
                refresh_token=self.credentials.tokens.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=self.credentials.tokens.scope.split()
                if self.credentials.tokens.scope
                else None,
            )

            self.service = build(
                "gmail",
                "v1",
                credentials=google_credentials,
                cache_discovery=False,
            )

            logger.info(
                "Initialized Gmail client for '%s'.",
                self.credentials.user_id,
            )

        except Exception as exc:
            logger.exception(
                "Failed to initialize Gmail API client."
            )

            raise EmailFetchError(
                "Unable to initialize Gmail API client."
            ) from exc

    def fetch_recent_messages(
        self,
        max_results: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches complete Gmail message payloads.
        """
        if self.service is None:
            raise EmailFetchError(
                "Gmail client is not authenticated."
            )

        limit = max_results or self.config.max_results

        try:
            message_refs = self._fetch_message_list(
                limit,
                query,
            )

            return [
                self._fetch_full_message(msg["id"])
                for msg in message_refs
            ]

        except HttpError as exc:
            raise EmailFetchError(
                f"Failed to fetch Gmail messages: {exc}"
            ) from exc

    def _fetch_message_list(
        self,
        limit: int,
        query: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        Retrieves message IDs matching the supplied query.
        """
        response = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                maxResults=limit,
                q=query,
            )
            .execute()
        )

        return response.get("messages", [])

    def _fetch_full_message(
        self,
        message_id: str,
    ) -> Dict[str, Any]:
        """
        Retrieves the complete Gmail payload for a single message.
        """
        return (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="full",
            )
            .execute()
        )