"""
Domain-specific exception hierarchy for the Authentication Subsystem.
"""

class AuthError(Exception):
    """Base exception for all authentication subsystem errors."""
    pass


class AuthenticationError(AuthError):
    """Raised when authentication flow, credential validation, or login fails."""
    pass


class TokenRefreshError(AuthError):
    """Raised when access token refresh via refresh token fails."""
    pass


class CredentialStoreError(AuthError):
    """Raised when storing, reading, or decrypting credentials fails."""
    pass


class OAuthCallbackError(AuthError):
    """Raised when OAuth 2.0 web authorization code exchange callback fails."""
    pass


class SessionExpiredError(AuthError):
    """Raised when a user authentication session has expired or is invalid."""
    pass
