"""
Execution layer exceptions hierarchy.
"""

from __future__ import annotations


class ExecutionError(Exception):
    """
    Base exception for all execution layer failures.
    """

    pass


class ExecutionValidationError(ExecutionError):
    """
    Raised when validation of the execution plan, action, or context preconditions fail.
    """

    pass


class ProviderExecutionError(ExecutionError):
    """
    Raised when a provider encounters a failure while coordinating or translating an action.
    """

    pass


class ProviderAPIError(ProviderExecutionError):
    """
    Raised when the underlying provider API (e.g. Gmail API client) returns an error response.
    """

    pass


class ExecutionAuthError(ProviderExecutionError):
    """
    Raised when credentials or token refresh operations fail during execution.
    """

    pass


class PartialExecutionError(ExecutionError):
    """
    Raised when some actions within an execution sequence fail, while others succeed.
    """

    def __init__(self, message: str, completed_actions: list, failed_actions: list) -> None:
        super().__init__(message)
        self.completed_actions = completed_actions
        self.failed_actions = failed_actions
