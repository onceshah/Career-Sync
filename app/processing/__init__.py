"""
Enterprise Email Processing Service package.
"""

from .config import ProcessingConfig
from .exceptions import (
    ConfigurationValidationError,
    LifecycleError,
    PipelineExecutionError,
    PollingError,
    ProcessingServiceError,
)
from .interfaces import (
    LifecycleOperations,
    PipelineRunner,
    PollingProvider,
    RetryOperations,
)
from .models import ProcessingContext, ProcessingState, ServiceMetrics

__all__ = [
    "ProcessingConfig",
    "ProcessingContext",
    "ProcessingState",
    "ServiceMetrics",
    "PipelineRunner",
    "PollingProvider",
    "RetryOperations",
    "LifecycleOperations",
    "ProcessingServiceError",
    "ConfigurationValidationError",
    "PollingError",
    "PipelineExecutionError",
    "LifecycleError",
]
