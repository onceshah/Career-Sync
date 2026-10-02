"""
OAuth 2.0 Web Authentication Service implementing AuthProvider.

Handles authorization URL generation, authorization code exchange, access token refreshing,
and credential revocation without any desktop popup flows.
"""

import os
import logging

import urllib.request
import urllib.parse


from google.oauth2.credentials import Credentials



from datetime import datetime, timedelta, timezone
from typing import Optional

from .exceptions import (
    AuthenticationError,
    OAuthCallbackError,
    TokenRefreshError,
)

from .interfaces import AuthProvider
from .models import OAuthToken
from ..infrastructure.config.auth_config import AuthConfig

logger = logging.getLogger(__name__)


class OAuthService(AuthProvider):
    """
    Production-grade OAuth 2.0 Web Authentication provider.
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Constructor dependency injection for AuthConfig.

        Args:
            config: AuthConfig settings instance.
        """
        from typing import Optional
        from google_auth_oauthlib.flow import Flow

        ...

        self._flow: Optional[Flow] = None
        self.config = config or AuthConfig()
        self.is_mocked = self.config.client_id.startswith("mock") and not os.path.exists(self.config.client_secrets_file or "")

    def generate_authorization_url(self, state: str) -> str:
        """
        Generates the external OAuth 2.0 web authorization URL.

        Args:
            state: Cryptographic state parameter to prevent CSRF attacks.

        Returns:
            Authorization URL string to redirect user browser.
        """
        if self.is_mocked:
            logger.info("Generating Mock Authorization URL.")
            params = {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
            return (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                f"{urllib.parse.urlencode(params)}"
            )

        try:
            self._flow = self._build_flow(state=state)

            auth_url, _ = self._flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )

            logger.info(
                "Generated web authorization URL with state token '%s...'.",
                state[:8],
            )

            return auth_url

        except Exception as exc:
            logger.exception("Failed to generate authorization URL.")
            raise AuthenticationError(
                f"OAuth authorization URL generation failed: {exc}"
            ) from exc

    def exchange_code_for_tokens(
        self,
        code: str,
        state: str,
    ) -> OAuthToken:
        """
        Exchanges authorization code received in web callback
        for an OAuthToken object.
        """

        if not code:
            raise OAuthCallbackError(
                "Missing authorization code in callback."
            )

        if self.is_mocked:
            logger.info("Exchanging Mock Authorization Code for OAuth Tokens.")

            now_utc = datetime.now(timezone.utc)

            return OAuthToken(
                access_token=f"mock_access_token_{code}",
                refresh_token=f"mock_refresh_token_{code}",
                token_type="Bearer",
                expires_at=now_utc + timedelta(hours=1),
                scope=" ".join(self.config.scopes),
            )

        if self._flow is None:
            raise OAuthCallbackError(
                "OAuth flow was not initialized."
            )

        try:
            self._flow.fetch_token(code=code)

            credentials = self._flow.credentials

            expires_at = credentials.expiry
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            token = OAuthToken(
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_type="Bearer",
                expires_at=expires_at,
                scope=(
                    " ".join(credentials.scopes)
                    if credentials.scopes
                    else None
                ),
                id_token=credentials.id_token,
            )

            logger.info(
                "Successfully exchanged authorization code for OAuth tokens."
            )

            return token

        except Exception as exc:
            logger.exception(
                "Failed to exchange authorization code for tokens."
            )

            raise OAuthCallbackError(
                f"OAuth token exchange failed: {exc}"
            ) from exc

        finally:
            # Always discard the flow after the exchange.
            self._flow = None

    def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        """
        Uses refresh_token to obtain a new access token from the provider.

        Args:
            refresh_token: Refresh token string.

        Returns:
            New OAuthToken instance with updated access token and expiration.
        """
        if not refresh_token:
            raise TokenRefreshError("Cannot refresh access token: refresh_token is missing.")

        if self.is_mocked or refresh_token.startswith("mock"):
            logger.info("Refreshing Mock OAuth Access Token.")
            now_utc = datetime.now(timezone.utc)
            return OAuthToken(
                access_token=f"mock_refreshed_access_token_{int(now_utc.timestamp())}",
                refresh_token=refresh_token,
                token_type="Bearer",
                expires_at=now_utc + timedelta(hours=1),
                scope=" ".join(self.config.scopes)
            )

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            google_creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=self.config.token_uri,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scopes=self.config.scopes
            )
            google_creds.refresh(Request())

            expires_at = google_creds.expiry
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            logger.info("Successfully refreshed OAuth access token.")
            return OAuthToken(
                access_token=google_creds.token,
                refresh_token=google_creds.refresh_token or refresh_token,
                token_type="Bearer",
                expires_at=expires_at,
                scope=" ".join(google_creds.scopes) if google_creds.scopes else None
            )
        except Exception as exc:
            logger.error(f"Failed to refresh access token: {exc}")
            raise TokenRefreshError(f"Token refresh failed: {exc}") from exc

    def revoke_credentials(self, token: str) -> bool:
        """
        Revokes access or refresh token with OAuth provider.

        Args:
            token: Access or refresh token to revoke.

        Returns:
            True if revocation succeeded.
        """
        if not token or self.is_mocked or token.startswith("mock"):
            logger.info("Revoked Mock OAuth token.")
            return True

        try:
            req = urllib.request.Request(
                f"{self.config.revoke_uri}?token={token}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info("Successfully revoked OAuth token with provider.")
                    return True
            return False
        except Exception as exc:
            logger.warning(f"Failed to revoke token with provider: {exc}")
            return False

    def _build_flow(self, state: Optional[str] = None):
        """Constructs google_auth_oauthlib Flow object for Web Authorization Code Flow."""
        from google_auth_oauthlib.flow import Flow

        if self.config.client_secrets_file and os.path.exists(self.config.client_secrets_file):
            return Flow.from_client_secrets_file(
                self.config.client_secrets_file,
                scopes=self.config.scopes,
                state=state,
                redirect_uri=self.config.redirect_uri
            )
        else:
            client_config = {
                "web": {
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "auth_uri": self.config.auth_uri,
                    "token_uri": self.config.token_uri,
                    "redirect_uris": [self.config.redirect_uri]
                }
            }
            return Flow.from_client_config(
                client_config,
                scopes=self.config.scopes,
                state=state,
                redirect_uri=self.config.redirect_uri
            )
        
    def get_authenticated_user_email(self, token: OAuthToken) -> str:
                """
                Returns the authenticated Gmail address.
                """

                try:
                    from google.oauth2.credentials import Credentials
                    from googleapiclient.discovery import build

                    creds = Credentials(
                        token=token.access_token,
                        refresh_token=token.refresh_token,
                        token_uri=self.config.token_uri,
                        client_id=self.config.client_id,
                        client_secret=self.config.client_secret,
                        scopes=self.config.scopes
                    )

                    service = build(
                        "gmail",
                        "v1",
                        credentials=creds,
                        cache_discovery=False
                    )

                    profile = (
                        service.users()
                        .getProfile(userId="me")
                        .execute()
                    )

                    return profile["emailAddress"]

                except Exception as exc:
                    logger.exception("Failed to retrieve authenticated Gmail address.")
                    raise AuthenticationError(
                        "Unable to retrieve authenticated Gmail address."
                    ) from exc
            
