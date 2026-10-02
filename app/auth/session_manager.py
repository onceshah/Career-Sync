"""
SessionManager implementation managing user web sessions and automatic token refresh workflows.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from app.auth.exceptions import AuthenticationError, TokenRefreshError
from app.auth.interfaces import AuthProvider, CredentialStore, SessionManager
from app.auth.models import AuthSession, AuthStatus, UserCredentials
# from app.auth.credential_store import MemoryCredentialStore, SQLiteCredentialStore
from app.auth.credential_store import MemoryCredentialStore
from app.auth.oauth_service import OAuthService

logger = logging.getLogger(__name__)


class SessionManagerImpl(SessionManager):
    """
    Production-grade SessionManager orchestrating web sessions, credential stores, and automatic token refresh.
    """

    def __init__(
        self,
        credential_store: Optional[CredentialStore] = None,
        auth_provider: Optional[AuthProvider] = None,
    ):
        """
        Constructor dependency injection for CredentialStore and AuthProvider.
        """

        self.credential_store = (
            credential_store or MemoryCredentialStore()
        )

        self.auth_provider = (
            auth_provider or OAuthService()
        )

        self._sessions: Dict[str, AuthSession] = {}

    def create_session(
        self,
        credentials: UserCredentials,
    ) -> AuthSession:
        """
        Creates an authenticated session for the supplied user credentials.

        Args:
            credentials:
                Authenticated provider credentials.

        Returns:
            Newly created AuthSession.
        """

        session_id = f"sess_{uuid.uuid4().hex}"

        now_utc = datetime.now(timezone.utc)

        session = AuthSession(
            session_id=session_id,
            user_id=credentials.user_id,
            provider=credentials.provider,
            is_authenticated=True,
            created_at=now_utc,
            last_accessed_at=now_utc,
        )

        self._sessions[session_id] = session

        logger.info(
            "Created session '%s' for user '%s'.",
            session_id[:12],
            credentials.user_id,
        )

        return session

    def get_active_session(self, session_id: str) -> Optional[AuthSession]:
        """
        Retrieves active AuthSession for given session_id.
        """
        if not session_id or session_id not in self._sessions:
            return None
        session = self._sessions[session_id]
        if not session.is_authenticated:
            return None
        session.last_accessed_at = datetime.now(timezone.utc)
        return session

    def get_valid_credentials(self, user_id: str, provider: str = "gmail") -> UserCredentials:
        """
        Retrieves valid UserCredentials for user_id, automatically refreshing access tokens if expired.

        Args:
            user_id: User identifier.
            provider: Target provider name.

        Returns:
            Valid UserCredentials instance.

        Raises:
            AuthenticationError: If credentials do not exist.
            TokenRefreshError: If token is expired and refresh fails.
        """
        credentials = self.credential_store.get_credentials(user_id=user_id, provider=provider)
        if credentials is None:
            raise AuthenticationError(
                f"No credentials found for '{user_id}'."
            )

        # Check token expiration & automatically trigger refresh
        if credentials.tokens.is_expired():

            logger.info(
                "Refreshing expired OAuth token for '%s'.",
                user_id,
            )

            refresh_token = credentials.tokens.refresh_token

            if not refresh_token:
                raise TokenRefreshError(
                    f"No refresh token available for '{user_id}'."
                )

            credentials.tokens = (
                self.auth_provider.refresh_access_token(
                    refresh_token
                )
            )

            credentials.updated_at = datetime.now(timezone.utc)

            self.credential_store.update_credentials(
                credentials
            )

            logger.info(
                "Successfully refreshed credentials for '%s'.",
                user_id,
            )

        return credentials


    def terminate_session(self, session_id: str) -> bool:
        """
        Terminates an active session, revokes tokens, and deletes credentials.

        Args:
            session_id: Active session ID.

        Returns:
            True if session was found and terminated.
        """
        session = self._sessions.pop(
            session_id,
            None,
        )

        if session is None:
            return False

        user_id = session.user_id
        provider = session.provider
        session.is_authenticated = False

        # Retrieve and revoke tokens if present
        creds = self.credential_store.get_credentials(user_id=user_id, provider=provider)
        if creds and creds.tokens.access_token:
            self.auth_provider.revoke_credentials(creds.tokens.access_token)

        self.credential_store.delete_credentials(user_id=user_id, provider=provider)
        logger.info(f"Terminated session '{session_id[:12]}...' and deleted credentials for user '{user_id}'.")
        return True

    def get_auth_status(self, session_id: Optional[str]) -> AuthStatus:
        """
        Returns AuthStatus for active session.
        """
        if session_id is None:
            return AuthStatus(is_authenticated=False)

        session = self.get_active_session(session_id)

        if session is None:
            return AuthStatus(is_authenticated=False)

        credentials = self.credential_store.get_credentials(
            user_id=session.user_id,
            provider=session.provider,
        )

        if credentials is None:
            return AuthStatus(is_authenticated=False)

        scopes_list = credentials.tokens.scope.split() if credentials.tokens.scope else []
        return AuthStatus(
            is_authenticated=True,
            user_id=session.user_id,
            provider=session.provider,
            token_expires_at=credentials.tokens.expires_at,
            scopes=scopes_list
        )
