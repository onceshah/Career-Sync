"""
Ollama LLM provider for the Enterprise AI Decision Pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import time

import requests

from app.ai.models import Prompt
from app.ai.interfaces import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    Provider responsible for communicating with a locally hosted Ollama server.
    """

    def __init__(
        self,
        host: str = None,
        model: str = None,
        timeout: int = 120,
        temperature: float = 0.0,
        num_predict: int = 512,
        num_ctx: int = 4096,
    ) -> None:
        # Environment-first configuration (OLLAMA_BASE_URL / OLLAMA_MODEL),
        # falling back to local dev defaults when not set.
        self.host = (host or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.timeout = timeout
        self.temperature = temperature
        self.num_predict = num_predict
        self.num_ctx = num_ctx

    @property
    def generate_url(self) -> str:
        return f"{self.host}/api/generate"

    def generate(self, prompt: Prompt) -> str:
        """
        Sends the prompt to Ollama and returns the raw response text.
        """
        prompt_text = (
            f"{prompt.system_prompt}\n\n"
            f"{prompt.user_prompt}"
        )
        prompt_char_count = len(prompt_text)

        payload = {
            "model": self.model,
            "prompt": prompt_text,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx,
            }
        }

        logger.info(
            "Sending request to Ollama model '%s' (Prompt size: %d characters)",
            self.model,
            prompt_char_count,
        )

        start_time = time.perf_counter()

        try:
            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            url = self.generate_url
            status_code = None
            response_body = None

            if exc.response is not None:
                status_code = exc.response.status_code
                response_body = exc.response.text
                if exc.response.url:
                    url = exc.response.url

            error_msg = (
                f"HTTP failure communicating with Ollama provider.\n"
                f"Request URL: {url}\n"
                f"Status Code: {status_code}\n"
                f"Response Body: {response_body}"
            )
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from exc

        duration = time.perf_counter() - start_time
        logger.info(
            "Ollama model '%s' responded in %.2f seconds.",
            self.model,
            duration,
        )

        try:
            body = response.json()

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned an invalid JSON response."
            ) from exc

        completion = body.get("response")

        if not completion:
            raise RuntimeError(
                "Ollama response does not contain a completion."
            )

        logger.info("Successfully received LLM response.")

        return completion.strip()