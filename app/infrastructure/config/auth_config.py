"""
Configuration parameters for OAuth 2.0 Web Authentication and credential persistence.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """
    Provider-independent configuration model for OAuth 2.0 Web Authentication.
    """
    client_id: str = Field(default="mock_client_id", description="OAuth 2.0 Client ID")
    client_secret: str = Field(default="mock_client_secret", description="OAuth 2.0 Client Secret")
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="OAuth 2.0 Web Authorization callback URL"
    )
    auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth",
        description="OAuth 2.0 Provider Authorization Endpoint"
    )
    token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="OAuth 2.0 Provider Token Endpoint"
    )
    revoke_uri: str = Field(
        default="https://oauth2.googleapis.com/revoke",
        description="OAuth 2.0 Provider Revocation Endpoint"
    )
    scopes: List[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        description="OAuth 2.0 Requested Scopes"
    )
    database_path: str = Field(default="auth_credentials.db", description="Path to SQLite auth database")
    encryption_key: Optional[str] = Field(default=None, description="Master secret key for Fernet token encryption")
    client_secrets_file: Optional[str] = Field(default="credentials/google_oauth_client.json", description="Optional Google credentials JSON file path")
