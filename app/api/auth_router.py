"""
Authentication router re-export for the CareerSync HTTP API.

The OAuth 2.0 endpoints (``/auth/login``, ``/auth/callback``, ``/auth/logout``,
``/auth/status``) are implemented in :mod:`app.auth.routes`; this module simply
re-exports them so the API package has a single, stable import surface.
"""

from app.auth.routes import router

__all__ = ["router"]
