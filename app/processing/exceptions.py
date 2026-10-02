"""
Custom exception hierarchy for the processing package.
"""

from __future__ import annotations


class ProcessingServiceError(Exception):
    """Base exception for all processing service errors."""

    pass


class ConfigurationValidationError(ProcessingServiceError):
    """Raised when runtime service configurations fail validation checks."""

    pass


class PollingError(ProcessingServiceError):
    """Raised when email fetching or polling operations fail."""

    pass


class PipelineExecutionError(ProcessingServiceError):
    """Raised when a permanent error occurs during the structured triage pipeline execution."""

    pass


class LifecycleError(ProcessingServiceError):
    """Raised when state transitions or service control commands are invalid."""

    pass
