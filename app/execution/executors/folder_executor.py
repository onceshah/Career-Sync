"""
FolderExecutor implementation for Gmail folder/label movements.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.errors import HttpError
from app.planning.models import PlannedAction
from app.execution.exceptions import ProviderAPIError, ExecutionValidationError
from app.execution.models import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ExecutionContext,
)

logger = logging.getLogger(__name__)


class FolderExecutor:
    """
    Executes folder movement operations in Gmail by mapping folders to nested labels
    and removing messages from the INBOX system label.
    """

    def execute(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes email moves.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "FolderExecutor processing action '%s' for email '%s' (dry-run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        # 1. Parameter Extraction & Validation
        folder_path = action.parameters.get("folder")
        if not folder_path:
            raise ExecutionValidationError(
                f"FolderExecutor requires a 'folder' parameter. Found: {action.parameters}"
            )

        label_name = str(folder_path).strip()

        # 2. Dry-Run Handling
        if context.dry_run:
            logger.info(
                "[DRY-RUN] Simulated moving email '%s' to folder label '%s' (archiving from INBOX).",
                email_id,
                label_name,
            )
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.DRY_RUN,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={"simulated_folder": label_name, "dry_run": True},
            )

        # 3. Live Gmail API Execution
        service = context.client
        try:
            # 3.1 Get existing labels, using execution context cache if available
            existing_labels = context.metadata.get("gmail_labels_cache")
            if existing_labels is None:
                labels_list = service.users().labels().list(userId="me").execute()
                existing_labels = labels_list.get("labels", [])
                context.metadata["gmail_labels_cache"] = existing_labels

            # Find matching label ID
            label_id = None
            for lbl in existing_labels:
                if lbl["name"].lower() == label_name.lower():
                    label_id = lbl["id"]
                    break

            # 3.2 Create nested label if missing
            if not label_id:
                logger.info("Folder label '%s' not found. Creating label.", label_name)
                label_body = {
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                }
                created_label = service.users().labels().create(userId="me", body=label_body).execute()
                label_id = created_label["id"]
                # Update cache
                existing_labels.append({"id": label_id, "name": label_name})
                logger.info("Successfully created folder label '%s' with ID '%s'.", label_name, label_id)

            # 3.3 Apply target label and remove from INBOX (unless target is INBOX itself)
            add_labels = [label_id]
            remove_labels = []

            # Check if the target is NOT inbox or equivalent system label
            if label_id != "INBOX" and label_name.upper() != "INBOX":
                remove_labels.append("INBOX")

            modify_body = {
                "addLabelIds": add_labels,
                "removeLabelIds": remove_labels,
            }

            service.users().messages().modify(userId="me", id=email_id, body=modify_body).execute()
            logger.info(
                "Successfully moved email '%s' to folder '%s' (add: %s, remove: %s).",
                email_id,
                label_name,
                add_labels,
                remove_labels,
            )

            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SUCCESS,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={
                    "folder": label_name,
                    "label_id": label_id,
                    "archived_from_inbox": "INBOX" in remove_labels,
                },
            )

        except HttpError as exc:
            logger.error("Gmail API error during folder move operations: %s", exc)
            raise ProviderAPIError(f"Gmail API failure during folder execution: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in FolderExecutor: %s", exc)
            raise ProviderAPIError(f"Unexpected error in FolderExecutor: {exc}") from exc
