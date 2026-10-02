"""
Execution provider registry.
"""

from __future__ import annotations

import logging
from typing import Dict, Type

from app.execution.interfaces import ExecutionProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Global registry for ExecutionProviders.
    """

    _providers: Dict[str, ExecutionProvider | Type[ExecutionProvider]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        provider: ExecutionProvider | Type[ExecutionProvider],
    ) -> None:
        """
        Registers an execution provider implementation under a given name.
        """
        name_key = name.lower().strip()
        cls._providers[name_key] = provider
        logger.info("Registered execution provider '%s'.", name_key)

    @classmethod
    def get_provider(cls, name: str) -> ExecutionProvider:
        """
        Resolves and returns a registered ExecutionProvider instance.
        """
        # Force loading the providers package to trigger module-level auto-registration
        import app.execution.providers  # noqa: F401

        name_key = name.lower().strip()
        provider = cls._providers.get(name_key)
        if not provider:
            raise ValueError(f"No execution provider registered under name '{name_key}'.")

        if isinstance(provider, type):
            try:
                return provider()
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to instantiate registered provider class '{name_key}': {exc}"
                ) from exc

        return provider
