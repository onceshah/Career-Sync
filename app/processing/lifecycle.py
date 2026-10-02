"""
Lifecycle manager implementation for controlling service state transitions and graceful cancellations.
"""

from __future__ import annotations

import logging
import threading

from app.processing.exceptions import LifecycleError
from app.processing.interfaces import LifecycleOperations
from app.processing.models import ProcessingState

logger = logging.getLogger(__name__)

# State Transition Matrix defining allowed states from any given state
ALLOWED_TRANSITIONS = {
    ProcessingState.INITIALIZING: {ProcessingState.STARTING, ProcessingState.STOPPED},
    ProcessingState.STARTING: {ProcessingState.RUNNING, ProcessingState.STOPPED},
    ProcessingState.RUNNING: {ProcessingState.IDLE, ProcessingState.PROCESSING, ProcessingState.STOPPING},
    ProcessingState.IDLE: {ProcessingState.PROCESSING, ProcessingState.STOPPING},
    ProcessingState.PROCESSING: {ProcessingState.IDLE, ProcessingState.STOPPING},
    ProcessingState.STOPPING: {ProcessingState.STOPPED},
    ProcessingState.STOPPED: {ProcessingState.STARTING, ProcessingState.INITIALIZING},
}


class LifecycleManager(LifecycleOperations):
    """
    Manages thread-safe state machine transitions and shutdown requests.
    Keep platform-level OS signal bindings decoupled from this class.
    """

    def __init__(self, initial_state: ProcessingState = ProcessingState.STOPPED) -> None:
        self._state = initial_state
        self._shutdown_requested = False
        self._lock = threading.Lock()

    @property
    def current_state(self) -> ProcessingState:
        """
        Returns the current state in a thread-safe manner.
        """
        with self._lock:
            return self._state

    def transition_to(self, target_state: ProcessingState) -> None:
        """
        Transitions the state machine to target_state following the ALLOWED_TRANSITIONS rules.
        """
        with self._lock:
            current = self._state
            if current == target_state:
                return

            allowed_targets = ALLOWED_TRANSITIONS.get(current, set())
            if target_state not in allowed_targets:
                raise LifecycleError(
                    f"Forbidden lifecycle state transition: {current.value} -> {target_state.value}"
                )

            self._state = target_state
            logger.info("Lifecycle state transitioned: %s -> %s", current.value, target_state.value)

    @property
    def shutdown_requested(self) -> bool:
        """
        Returns the graceful shutdown request flag status in a thread-safe manner.
        """
        with self._lock:
            return self._shutdown_requested

    def request_shutdown(self) -> None:
        """
        Sets the shutdown flag and transitions states to STOPPING.
        """
        with self._lock:
            if self._shutdown_requested:
                return

            logger.info("Graceful shutdown request received.")
            self._shutdown_requested = True

            # Shift state automatically to STOPPING if in active cycles
            if self._state in (ProcessingState.RUNNING, ProcessingState.IDLE, ProcessingState.PROCESSING):
                logger.info(
                    "Lifecycle state transitioned (auto-stopping): %s -> %s",
                    self._state.value,
                    ProcessingState.STOPPING.value,
                )
                self._state = ProcessingState.STOPPING

    def reset(self) -> None:
        """
        Resets the lifecycle status back to default for clean restarts or test suites.
        """
        with self._lock:
            self._state = ProcessingState.STOPPED
            self._shutdown_requested = False
            logger.info("Lifecycle status reset to default (STOPPED).")
