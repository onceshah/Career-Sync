"""
Domain data models for authentication tokens, credentials, and session state.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class OAuthToken(BaseModel):
    """
    Encapsulates OAuth 2.0 access and refresh token data.
    """
    access_token: str = Field(..., description="OAuth 2.0 Access Token")
    refresh_token: Optional[str] = Field(default=None, description="OAuth 2.0 Refresh Token")
    token_type: str = Field(default="Bearer", description="Token Type (e.g. Bearer)")
    expires_at: Optional[datetime] = Field(default=None, description="UTC expiration datetime of access token")
    scope: Optional[str] = Field(default=None, description="Granted scope string")
    id_token: Optional[str] = Field(default=None, description="Optional OpenID Connect ID Token")

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Checks if the access token is expired or about to expire within buffer_seconds.
        """
        if not self.expires_at:
            return False
        now_utc = datetime.now(timezone.utc)
        expires_at_utc = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return (expires_at_utc.timestamp() - now_utc.timestamp()) <= buffer_seconds


class UserCredentials(BaseModel):
    """
    Provider-independent container for stored user credentials.
    """
    user_id: str = Field(..., description="Unique user identifier or email address")
    provider: str = Field(default="gmail", description="Email provider key (e.g. gmail, outlook, imap)")
    tokens: OAuthToken = Field(..., description="Associated OAuth 2.0 token object")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Credential creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")


class AuthSession(BaseModel):
    """
    Represents an active authenticated user web session.
    """
    session_id: str = Field(..., description="Unique web session token")
    user_id: str = Field(..., description="Authenticated user ID")
    provider: str = Field(default="gmail", description="Target provider")
    is_authenticated: bool = Field(default=True, description="Session authentication state")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OAuthState(BaseModel):
    """
    CSRF state parameter model stored during OAuth login redirect.
    """
    state_token: str = Field(..., description="Random secure state token")
    redirect_uri: str = Field(..., description="Configured callback URL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthStatus(BaseModel):
    """
    Public response model indicating current authentication status.
    """
    is_authenticated: bool = Field(..., description="Whether user session is valid and authenticated")
    user_id: Optional[str] = Field(default=None, description="User identifier if logged in")
    provider: Optional[str] = Field(default=None, description="Email provider key")
    token_expires_at: Optional[datetime] = Field(default=None, description="Access token expiration timestamp")
    scopes: List[str] = Field(default_factory=list, description="Active granted OAuth scopes")
