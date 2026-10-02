"""
Gmail Execution Provider.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.domain.enums import ActionType
from app.planning.models import PlannedAction
from app.execution.interfaces import ExecutionProvider
from app.execution.models import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ExecutionContext,
)
from app.execution.providers.registry import ProviderRegistry
from app.execution.executors.archive_executor import ArchiveExecutor
from app.execution.executors.flag_executor import FlagExecutor
from app.execution.executors.folder_executor import FolderExecutor
from app.execution.executors.label_executor import LabelExecutor

logger = logging.getLogger(__name__)


class GmailExecutionProvider(ExecutionProvider):
    """
    Gmail implementation of ExecutionProvider acting as a dispatcher to specialized executors.
    """

    def __init__(self) -> None:
        self.label_executor = LabelExecutor()
        self.folder_executor = FolderExecutor()
        self.flag_executor = FlagExecutor()
        self.archive_executor = ArchiveExecutor()

    def execute_action(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Translates a provider-independent action into Gmail execution steps via dispatcher.
        """
        logger.info(
            "Gmail provider executing action '%s' for email '%s' (dry_run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        if action.action == ActionType.ADD_CATEGORY:
            return self.label_executor.execute(action, email_id, context)

        elif action.action == ActionType.MOVE_TO_FOLDER:
            return self.folder_executor.execute(action, email_id, context)

        elif action.action in (ActionType.FLAG_FOR_REVIEW, ActionType.ESCALATE):
            return self.flag_executor.execute(action, email_id, context)

        elif action.action in (ActionType.ARCHIVE, ActionType.IGNORE):
            return self.archive_executor.execute(action, email_id, context)

        else:
            logger.warning("Action type '%s' is not supported by the Gmail provider.", action.action)
            start = datetime.now(timezone.utc)
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SKIPPED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                error_message=f"Action type '{action.action}' is not supported by the Gmail provider.",
            )


# Auto-register Gmail execution provider
ProviderRegistry.register("gmail", GmailExecutionProvider)
