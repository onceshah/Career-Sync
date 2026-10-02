"""
ArchiveExecutor implementation for Gmail archive and ignore actions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.errors import HttpError

from app.domain.enums import ActionType
from app.planning.models import PlannedAction
from app.execution.exceptions import ProviderAPIError
from app.execution.models import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ExecutionContext,
)

logger = logging.getLogger(__name__)


class ArchiveExecutor:
    """
    Executes Gmail archive operations by removing the INBOX system label (and UNREAD label for ignore).
    """

    def execute(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes archiving or ignoring operations.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "ArchiveExecutor processing action '%s' for email '%s' (dry-run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        remove_labels = ["INBOX"]
        if action.action == ActionType.IGNORE:
            remove_labels.append("UNREAD")

        # Dry-run Handling
        if context.dry_run:
            logger.info(
                "[DRY-RUN] Simulated removing labels %s from email '%s'.",
                remove_labels,
                email_id,
            )
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.DRY_RUN,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={"simulated_removals": remove_labels, "dry_run": True},
            )

        # Live Execution
        service = context.client
        try:
            modify_body = {
                "addLabelIds": [],
                "removeLabelIds": remove_labels,
            }

            service.users().messages().modify(userId="me", id=email_id, body=modify_body).execute()
            logger.info("Successfully archived email '%s' by removing labels: %s.", email_id, remove_labels)

            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SUCCESS,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={"removed_labels": remove_labels},
            )

        except HttpError as exc:
            logger.error("Gmail API error during archive operations: %s", exc)
            raise ProviderAPIError(f"Gmail API failure during archive execution: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in ArchiveExecutor: %s", exc)
            raise ProviderAPIError(f"Unexpected error in ArchiveExecutor: {exc}") from exc
