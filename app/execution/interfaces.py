"""
Interfaces for execution providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.planning.models import PlannedAction
from app.execution.models import ActionExecutionResult, ExecutionContext


class ExecutionProvider(ABC):
    """
    Interface defining the execution capabilities that every email provider must supply.
    """

    @abstractmethod
    def execute_action(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes a single provider-independent planned action against the provider.

        Parameters
        ----------
        action : PlannedAction
            The planned action containing the ActionType and parameters.
        email_id : str
            Identifier of the email target (e.g. message_id).
        context : ExecutionContext
            The execution-scoped context carrying client dependencies and configuration.

        Returns
        -------
        ActionExecutionResult
            The outcome of executing this specific action.
        """
        raise NotImplementedError
