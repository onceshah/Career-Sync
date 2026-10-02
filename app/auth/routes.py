"""
FastAPI router definition exposing production-grade OAuth 2.0 Web Authentication endpoints.
"""

import uuid
import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth.exceptions import AuthError
from app.auth.interfaces import AuthProvider, CredentialStore, SessionManager
from app.auth.models import AuthStatus, OAuthToken, UserCredentials
from app.auth.oauth_service import OAuthService
from app.auth.credential_store import MemoryCredentialStore
from app.auth.session_manager import SessionManagerImpl

logger = logging.getLogger(__name__)

# Temporary in-memory store for CSRF state parameters
_oauth_states: Dict[str, str] = {}

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Global singleton dependencies for FastAPI router DI injection
_auth_service = OAuthService()
_credential_store = MemoryCredentialStore()
_session_manager = SessionManagerImpl(credential_store=_credential_store, auth_provider=_auth_service)


def get_auth_service() -> AuthProvider:
    return _auth_service


def get_credential_store() -> CredentialStore:
    return _credential_store


def get_session_manager() -> SessionManager:
    return _session_manager


@router.get("/login", summary="Initiate OAuth 2.0 Web Authorization Flow")
def login(
    request: Request,
    provider: str = Query("gmail", description="Target email provider"),
    auth_service: AuthProvider = Depends(get_auth_service)
):
    """
    Generates OAuth 2.0 web authorization URL and redirects browser to login.
    """
    state_token = f"state_{uuid.uuid4().hex}"
    _oauth_states[state_token] = provider

    auth_url = auth_service.generate_authorization_url(state=state_token)
    logger.info(f"Initiated OAuth login redirect for provider '{provider}' (State: {state_token[:8]}...).")
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback", summary="OAuth 2.0 Web Authorization Callback")
def callback(
    response: Response,
    code: Optional[str] = Query(None, description="Authorization code from OAuth provider"),
    state: Optional[str] = Query(None, description="CSRF state parameter"),
    error: Optional[str] = Query(None, description="Error parameter if user denied access"),
    auth_service: AuthProvider = Depends(get_auth_service),
    credential_store: CredentialStore = Depends(get_credential_store),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Handles OAuth 2.0 web callback redirect, exchanges code for tokens, saves credentials, and sets session cookie.
    """
    if error:
        logger.warning(f"OAuth authorization denied by user or provider: {error}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth authorization error: {error}")

    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code or state token.")

    if state not in _oauth_states:
        logger.warning(f"Invalid or expired OAuth state token '{state}'.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF state token.")

    provider = _oauth_states.pop(state)

    try:
        token: OAuthToken = auth_service.exchange_code_for_tokens(code=code, state=state)
        user_id = f"user_{state[:8]}@enterprise.com"  # Example user ID extracted from token or default profile

        user_credentials = UserCredentials(
            user_id=user_id,
            provider=provider,
            tokens=token
        )
        credential_store.save_credentials(user_credentials)

        session = session_manager.create_session(credentials=user_credentials)

        response = RedirectResponse(url="/auth/status", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="session_id", value=session.session_id, httponly=True, samesite="lax")
        logger.info(f"OAuth callback successful for user '{user_id}'. Session created.")
        return response
    except AuthError as exc:
        logger.error(f"OAuth callback processing failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/logout", summary="Terminate Authenticated Session & Revoke Tokens")
def logout(
    request: Request,
    response: Response,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Terminates session, revokes tokens, deletes credentials, and clears session cookie.
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        session_manager.terminate_session(session_id)
        response.delete_cookie("session_id")
        logger.info(f"Successfully logged out session '{session_id[:12]}...'.")

    return {"message": "Successfully logged out."}


@router.get("/status", response_model=AuthStatus, summary="Check Authentication Status")
def auth_status(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Returns current web authentication status for session.
    """
    session_id = request.cookies.get("session_id")
    return session_manager.get_auth_status(session_id=session_id)
