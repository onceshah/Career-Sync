"""
Abstract base classes and interfaces defining strict contracts for the Authentication Subsystem.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.auth.models import AuthSession, AuthStatus, OAuthToken, UserCredentials


class AuthProvider(ABC):
    """
    Abstract interface for provider-agnostic OAuth 2.0 Web Authorization flows.
    """

    @abstractmethod
    def generate_authorization_url(self, state: str) -> str:
        """Generates the external OAuth 2.0 web authorization URL."""
        pass

    @abstractmethod
    def exchange_code_for_tokens(self, code: str, state: str) -> OAuthToken:
        """Exchanges authorization code received in callback for OAuthToken."""
        pass

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        """Uses refresh_token to retrieve a new OAuthToken."""
        pass

    @abstractmethod
    def revoke_credentials(self, token: str) -> bool:
        """Revokes an active access or refresh token with the OAuth provider."""
        pass


class CredentialStore(ABC):
    """
    Abstract interface for storing and retrieving encrypted user credentials.
    """

    @abstractmethod
    def save_credentials(self, credentials: UserCredentials) -> None:
        """Saves or updates user credentials in persistent store."""
        pass

    @abstractmethod
    def get_credentials(self, user_id: str, provider: str = "gmail") -> Optional[UserCredentials]:
        """Retrieves user credentials for given user_id and provider."""
        pass

    @abstractmethod
    def update_credentials(self, credentials: UserCredentials) -> None:
        """Updates existing user credentials."""
        pass

    @abstractmethod
    def delete_credentials(self, user_id: str, provider: str = "gmail") -> bool:
        """Deletes user credentials from store."""
        pass

    @abstractmethod
    def has_credentials(self, user_id: str, provider: str = "gmail") -> bool:
        """Checks if active credentials exist for user_id and provider."""
        pass


class SessionManager(ABC):
    """
    Abstract interface for managing web authentication sessions and credentials injection.
    """

    @abstractmethod
    def create_session(self, credentials: UserCredentials) -> AuthSession:
        """Creates a new authenticated web session for the supplied provider credentials."""
        pass

    @abstractmethod
    def get_active_session(self, session_id: str) -> Optional[AuthSession]:
        """Retrieves active AuthSession for session_id."""
        pass

    @abstractmethod
    def get_valid_credentials(self, user_id: str, provider: str = "gmail") -> UserCredentials:
        """Retrieves valid UserCredentials, automatically refreshing tokens if expired."""
        pass

    @abstractmethod
    def terminate_session(self, session_id: str) -> bool:
        """Terminates an active session and deletes cached credentials."""
        pass

    @abstractmethod
    def get_auth_status(self, session_id: Optional[str]) -> AuthStatus:
        """Returns AuthStatus for active session."""
        pass


class EmailProviderClient(ABC):
    """
    Abstract interface for provider-independent email API clients (Gmail, Outlook, IMAP).
    """

    @abstractmethod
    def fetch_recent_messages(self, max_results: Optional[int] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches raw message dictionary payloads from email provider API."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical name of the email provider (e.g. 'gmail', 'outlook')."""
        pass

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Returns True if client has valid credentials injected."""
        pass
