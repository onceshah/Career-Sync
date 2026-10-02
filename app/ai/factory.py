"""
Factory for constructing Enterprise AI providers.
"""

from __future__ import annotations

from app.ai.interfaces import LLMProvider
from app.ai.providers.ollama import OllamaProvider


class LLMProviderFactory:
    """
    Factory responsible for creating LLM provider implementations.
    """

    @staticmethod
    def create(
        provider: str = "ollama",
        **kwargs,
    ) -> LLMProvider:
        """
        Create and return the requested LLM provider.

        Parameters
        ----------
        provider : str
            Name of the provider implementation.

        Returns
        -------
        LLMProvider
        """

        provider = provider.lower()

        if provider == "ollama":
            return OllamaProvider(**kwargs)

        raise ValueError(
            f"Unsupported LLM provider: '{provider}'."
        )