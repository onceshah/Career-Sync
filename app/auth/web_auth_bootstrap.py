"""
OAuth Web Authentication Bootstrap.

Coordinates the complete browser-based
authentication flow.
"""

from __future__ import annotations

import secrets
import webbrowser

from .credential_store import CredentialStore
from .exceptions import AuthenticationError
from .models import UserCredentials
from .oauth_callback_server import OAuthCallbackServer
from .oauth_service import OAuthService


class WebAuthBootstrap:

    def __init__(
        self,
        oauth_service: OAuthService,
        credential_store: CredentialStore,
    ):

        self._oauth = oauth_service
        self._store = credential_store

    def authenticate(
        self,
    ) -> UserCredentials:

        state = secrets.token_urlsafe(32)

        auth_url = self._oauth.generate_authorization_url(
            state
        )

        callback_server = OAuthCallbackServer()

        webbrowser.open(auth_url)

        callback = callback_server.wait_for_callback()

        if callback.state != state:

            raise AuthenticationError(
                "OAuth state validation failed."
            )

        token = self._oauth.exchange_code_for_tokens(
            callback.code,
            callback.state,
        )

        email = self._oauth.get_authenticated_user_email(
            token
        )

        credentials = UserCredentials(
            user_id=email,
            provider="gmail",
            tokens=token,
        )

        self._store.save_credentials(
            credentials
        )

        return credentials