"""
Primary EmailProcessingService orchestration layer.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from app.processing.config import ProcessingConfig
from app.processing.interfaces import (
    LifecycleOperations,
    PipelineRunner,
    PollingProvider,
    RetryOperations,
)
from app.processing.models import (
    ProcessingContext,
    ProcessingState,
    ServiceMetrics,
)

logger = logging.getLogger(__name__)


class InMemoryLifecycleManager(LifecycleOperations):
    """
    Simple in-memory lifecycle manager for testing and standalone processing.
    """

    def __init__(self) -> None:
        self._state = ProcessingState.STOPPED
        self._shutdown_requested = False

    @property
    def current_state(self) -> ProcessingState:
        return self._state

    def transition_to(self, target_state: ProcessingState) -> None:
        logger.info("Lifecycle state transitioned: %s -> %s", self._state.value, target_state.value)
        self._state = target_state

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        logger.info("Shutdown signaled to lifecycle manager.")
        self._shutdown_requested = True
        self._state = ProcessingState.STOPPING


class EmailProcessingService:
    """
    Primary Application Service that orchestrates continuous polling,
    triaging, retries, and metrics tracking.
    """

    def __init__(
        self,
        config: ProcessingConfig,
        polling_manager: PollingProvider,
        retry_manager: RetryOperations,
        pipeline_runner: PipelineRunner,
        lifecycle_manager: Optional[LifecycleOperations] = None,
    ) -> None:
        self.config = config
        self.polling_manager = polling_manager
        self.retry_manager = retry_manager
        self.pipeline_runner = pipeline_runner
        self.lifecycle_manager = lifecycle_manager or InMemoryLifecycleManager()
        self.metrics = ServiceMetrics()

    def run_once(self, context: ProcessingContext) -> None:
        """
        Executes a single cycle of polling and processing a batch of emails sequentially.
        """
        if self.lifecycle_manager.shutdown_requested:
            logger.warning("Run cycle skipped because shutdown is requested.")
            return

        logger.info("Starting email processing cycle (session: %s)...", context.session_id)
        self.metrics.last_poll_at = datetime.now(timezone.utc)
        previous_state = self.lifecycle_manager.current_state
        self.lifecycle_manager.transition_to(ProcessingState.PROCESSING)

        try:
            # 1. Ingest batch of emails
            emails = self.polling_manager.poll_emails(context, self.config.batch_size)
            logger.info("Discovered %s email(s) during polling cycle.", len(emails))

            # 2. Process emails sequentially
            for email in emails:
                if self.lifecycle_manager.shutdown_requested:
                    logger.info("Shutdown request detected mid-batch. Aborting remaining emails.")
                    break

                email_id = email.headers.message_id if (email.headers and email.headers.message_id) else "unknown"
                logger.info("Processing email ID '%s'...", email_id)

                try:
                    # Execute the full pipeline under retry management
                    result = self.retry_manager.execute_with_retry(
                        lambda: self.pipeline_runner.run_pipeline(email, context),
                        context,
                    )
                    self.metrics.processed_count += 1
                    logger.info("Successfully triaged email '%s' (Result: %s).", email_id, result.status)

                except Exception as exc:
                    self.metrics.failure_count += 1
                    if self.retry_manager.is_transient(exc):
                        self.metrics.transient_failure_count += 1
                        logger.error("Transient cycle error on email '%s': %s", email_id, exc)
                    else:
                        self.metrics.permanent_failure_count += 1
                        logger.error("Permanent cycle error on email '%s': %s", email_id, exc)

        except Exception as exc:
            logger.error("Batch poll and processing cycle encountered an error: %s", exc)
            self.metrics.failure_count += 1
        finally:
            # Restore state
            if not self.lifecycle_manager.shutdown_requested:
                self.lifecycle_manager.transition_to(ProcessingState.IDLE)
            else:
                self.lifecycle_manager.transition_to(ProcessingState.STOPPING)

    def start(self, context: ProcessingContext) -> None:
        """
        Starts the continuous polling loop.
        """
        if self.lifecycle_manager.current_state == ProcessingState.RUNNING:
            logger.warning("Continuous processing loop is already running.")
            return

        logger.info("Starting EmailProcessingService daemon loop...")
        self.metrics.start_time = datetime.now(timezone.utc)
        self.lifecycle_manager.transition_to(ProcessingState.STARTING)
        self.lifecycle_manager.transition_to(ProcessingState.RUNNING)
        self.metrics.status = ProcessingState.RUNNING

        try:
            # Main Polling Loop
            while not self.lifecycle_manager.shutdown_requested:
                self.run_once(context)

                if self.lifecycle_manager.shutdown_requested:
                    break

                # Sleep in short increments to remain highly responsive to stops
                sleep_remaining = self.config.poll_interval_seconds
                logger.info("Daemon loop sleeping for %s seconds...", sleep_remaining)
                while sleep_remaining > 0 and not self.lifecycle_manager.shutdown_requested:
                    sleep_chunk = min(1.0, sleep_remaining)
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk

        finally:
            current = self.lifecycle_manager.current_state
            if current not in (ProcessingState.STOPPING, ProcessingState.STOPPED):
                try:
                    self.lifecycle_manager.transition_to(ProcessingState.STOPPING)
                except Exception:
                    pass
            self.lifecycle_manager.transition_to(ProcessingState.STOPPED)
            self.metrics.status = ProcessingState.STOPPED
            self.metrics.uptime_seconds = (
                (datetime.now(timezone.utc) - self.metrics.start_time).total_seconds()
                if self.metrics.start_time
                else 0.0
            )
            logger.info(
                "Daemon loop terminated. Total uptime: %s seconds.",
                int(self.metrics.uptime_seconds),
            )

    def stop(self) -> None:
        """
        Initiates a graceful shutdown of the service.
        """
        logger.info("Shutdown requested on EmailProcessingService.")
        self.lifecycle_manager.request_shutdown()
