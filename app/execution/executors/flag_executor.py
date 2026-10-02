"""
FlagExecutor implementation for Gmail starring and escalation flagging.
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


class FlagExecutor:
    """
    Executes flag/star/importance and escalation operations in Gmail.
    """

    def execute(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes starring or escalation labels.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "FlagExecutor processing action '%s' for email '%s' (dry-run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        labels_to_add = ["STARRED"]
        custom_labels_to_create = []

        if action.action == ActionType.ESCALATE:
            custom_labels_to_create.append("Escalated")
            labels_to_add.append("Escalated")

        # Dry-run Handling
        if context.dry_run:
            logger.info(
                "[DRY-RUN] Simulated applying labels %s to email '%s'.",
                labels_to_add,
                email_id,
            )
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.DRY_RUN,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={"simulated_labels": labels_to_add, "dry_run": True},
            )

        # Live Execution
        service = context.client
        try:
            # Reify custom labels, using context cache for existing labels if available
            existing_labels = context.metadata.get("gmail_labels_cache")

            for custom_lbl in custom_labels_to_create:
                if existing_labels is None:
                    labels_list = service.users().labels().list(userId="me").execute()
                    existing_labels = labels_list.get("labels", [])
                    context.metadata["gmail_labels_cache"] = existing_labels

                label_id = None
                for lbl in existing_labels:
                    if lbl["name"].lower() == custom_lbl.lower():
                        label_id = lbl["id"]
                        break

                if not label_id:
                    logger.info("Creating custom escalation label '%s'.", custom_lbl)
                    label_body = {
                        "name": custom_lbl,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    }
                    created = service.users().labels().create(userId="me", body=label_body).execute()
                    label_id = created["id"]
                    # Update cache
                    existing_labels.append({"id": label_id, "name": custom_lbl})

                # Substitute name with ID in add list
                labels_to_add = [label_id if x == custom_lbl else x for x in labels_to_add]

            modify_body = {
                "addLabelIds": labels_to_add,
                "removeLabelIds": [],
            }

            service.users().messages().modify(userId="me", id=email_id, body=modify_body).execute()
            logger.info("Successfully flagged email '%s' with labels: %s.", email_id, labels_to_add)

            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SUCCESS,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={"applied_labels": labels_to_add},
            )

        except HttpError as exc:
            logger.error("Gmail API error during flag operations: %s", exc)
            raise ProviderAPIError(f"Gmail API failure during flag execution: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in FlagExecutor: %s", exc)
            raise ProviderAPIError(f"Unexpected error in FlagExecutor: {exc}") from exc
