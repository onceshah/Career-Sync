"""
Interface contracts for the processing service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, TypeVar, List

from app.domain.models import StructuredEmail
from app.execution.models import ExecutionResult
from app.processing.models import ProcessingContext, ProcessingState

T = TypeVar("T")


class PipelineRunner(ABC):
    """
    Façade interface for executing the end-to-end email triage pipeline.
    """

    @abstractmethod
    def run_pipeline(
        self,
        email: StructuredEmail,
        context: ProcessingContext,
    ) -> ExecutionResult:
        """
        Runs the full triage pipeline (Policy -> AI -> Planning -> Execution) for a single email.
        """
        pass


class PollingProvider(ABC):
    """
    Interface for polling recent emails.
    """

    @abstractmethod
    def poll_emails(
        self,
        context: ProcessingContext,
        batch_size: int,
    ) -> List[StructuredEmail]:
        """
        Polls and returns a batch of emails for processing.
        """
        pass


class RetryOperations(ABC):
    """
    Interface for executing operations with retry logic.
    """

    @abstractmethod
    def execute_with_retry(
        self,
        operation: Callable[[], T],
        context: ProcessingContext,
    ) -> T:
        """
        Executes a callable, applying retry strategies for classified transient errors.
        """
        pass


class LifecycleOperations(ABC):
    """
    Interface for lifecycle management.
    """

    @property
    @abstractmethod
    def current_state(self) -> ProcessingState:
        """
        Returns the current state.
        """
        pass

    @abstractmethod
    def transition_to(self, target_state: ProcessingState) -> None:
        """
        Transition the state to target_state.
        """
        pass

    @property
    @abstractmethod
    def shutdown_requested(self) -> bool:
        """
        Returns True if a stop has been requested.
        """
        pass

    @abstractmethod
    def request_shutdown(self) -> None:
        """
        Signals that a shutdown has been requested.
        """
        pass
