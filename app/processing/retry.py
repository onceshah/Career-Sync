"""
Retry manager implementation for handling transient pipeline and execution failures.
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Callable, TypeVar

from googleapiclient.errors import HttpError
import requests

from app.execution.exceptions import (
    ExecutionAuthError,
    ExecutionValidationError,
)
from app.processing.config import ProcessingConfig
from app.processing.interfaces import RetryOperations
from app.processing.models import ProcessingContext

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryManager(RetryOperations):
    """
    Manages operational retries with exponential backoff and transient failure classification.
    """

    def __init__(self, config: ProcessingConfig) -> None:
        self.config = config

    def is_transient(self, exc: Exception) -> bool:
        """
        Classifies exceptions into transient (retryable) and permanent (non-retryable).
        """
        # Unpack wrapped exceptions to extract the root cause
        cause = exc.__cause__ or exc

        # 1. Permanent Validation & Authentication Exceptions
        if isinstance(cause, (ExecutionValidationError, ExecutionAuthError)):
            logger.debug("Exception classified as PERMANENT: %s", type(cause).__name__)
            return False

        # 2. Transient HTTP Client Exceptions
        if isinstance(cause, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            logger.debug("Exception classified as TRANSIENT: requests network timeout/connection error")
            return True

        if isinstance(cause, requests.exceptions.HTTPError):
            try:
                status_code = cause.response.status_code
                if status_code in (429, 500, 502, 503, 504):
                    logger.debug("Exception classified as TRANSIENT: requests HTTP status %s", status_code)
                    return True
            except AttributeError:
                pass

        # 3. Transient Low-level Socket / Connection Exceptions
        if isinstance(cause, (socket.timeout, ConnectionRefusedError, ConnectionResetError)):
            logger.debug("Exception classified as TRANSIENT: socket timeout/connection reset")
            return True

        # 4. Google API HttpError classification
        if isinstance(cause, HttpError):
            try:
                status_code = cause.resp.status
                # 429: Too Many Requests, 5xx: Server Errors
                if status_code in (429, 500, 502, 503, 504):
                    logger.debug("Exception classified as TRANSIENT: Google API status %s", status_code)
                    return True
            except AttributeError:
                pass
            logger.debug("Exception classified as PERMANENT: Google API status not transient")
            return False

        # 5. String-based heuristics for custom or third-party exceptions
        exc_str = str(cause).lower()
        if "rate limit" in exc_str or "timeout" in exc_str or "temporarily unavailable" in exc_str:
            logger.debug("Exception classified as TRANSIENT via heuristic matching")
            return True

        # Default to permanent for safety to avoid infinite loops on unhandled bugs
        logger.debug("Exception default-classified as PERMANENT: %s", type(cause).__name__)
        return False

    def execute_with_retry(
        self,
        operation: Callable[[], T],
        context: ProcessingContext,
    ) -> T:
        """
        Executes a callable with retries.
        """
        attempts = 0
        max_attempts = self.config.retry_count
        delay = self.config.retry_delay_seconds

        while True:
            try:
                return operation()
            except Exception as exc:
                attempts += 1

                # If we exceeded retry count, re-raise the exception
                if attempts > max_attempts:
                    logger.error(
                        "Max retry attempts (%s) exceeded. Last exception: %s",
                        max_attempts,
                        exc,
                    )
                    raise exc

                # Check if exception is transient
                if not self.is_transient(exc):
                    logger.warning(
                        "Permanent failure encountered (%s). Bypassing retry cycle.",
                        exc,
                    )
                    raise exc

                # Compute exponential backoff delay
                backoff_delay = delay * (self.config.backoff_multiplier ** (attempts - 1))
                logger.warning(
                    "Transient failure detected (%s). Retrying (attempt %s/%s) in %s seconds...",
                    exc,
                    attempts,
                    max_attempts,
                    backoff_delay,
                )

                time.sleep(backoff_delay)
