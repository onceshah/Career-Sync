"""
CredentialStore implementations for MVP.

Persistence has been intentionally disabled.
Only MemoryCredentialStore is active.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from app.auth.exceptions import CredentialStoreError
from app.auth.interfaces import CredentialStore
from app.auth.models import UserCredentials

logger = logging.getLogger(__name__)


class MemoryCredentialStore(CredentialStore):
    """
    Thread-safe in-memory credential store.

    Intended for:
        • Local development
        • OAuth testing
        • End-to-end pipeline demos
    """

    def __init__(self):
        self._store: Dict[Tuple[str, str], UserCredentials] = {}

    def save_credentials(self, credentials: UserCredentials) -> None:
        key = (credentials.user_id, credentials.provider)
        self._store[key] = credentials.model_copy(deep=True)

    def get_credentials(
        self,
        user_id: str,
        provider: str = "gmail"
    ) -> Optional[UserCredentials]:
        key = (user_id, provider)
        creds = self._store.get(key)
        return creds.model_copy(deep=True) if creds else None

    def update_credentials(self, credentials: UserCredentials) -> None:
        credentials.updated_at = datetime.now(timezone.utc)
        self.save_credentials(credentials)

    def delete_credentials(
        self,
        user_id: str,
        provider: str = "gmail"
    ) -> bool:
        key = (user_id, provider)

        if key in self._store:
            del self._store[key]
            return True

        return False

    def has_credentials(
        self,
        user_id: str,
        provider: str = "gmail"
    ) -> bool:
        return (user_id, provider) in self._store