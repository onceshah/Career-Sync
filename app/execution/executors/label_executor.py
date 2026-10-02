"""
LabelExecutor implementation for Gmail label operations.
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


class LabelExecutor:
    """
    Executes Gmail label operations: checking, creating, and applying labels to messages.
    """

    def execute(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes label creation and application.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "LabelExecutor processing action '%s' for email '%s' (dry-run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        # 1. Parameter Extraction & Validation
        labels_val = action.parameters.get("labels")
        if labels_val is not None:
            if isinstance(labels_val, list):
                labels = [str(l) for l in labels_val if l]
            else:
                labels = [str(labels_val)]
        else:
            # Fallback to single label / category parameters for backwards compatibility
            single_val = action.parameters.get("label") or action.parameters.get("category")
            if single_val:
                labels = [str(single_val)]
                logger.warning(
                    "ActionType.ADD_CATEGORY parameter 'label'/'category' is deprecated. "
                    "Please transition to the canonical contract 'labels: list[str]'."
                )
            else:
                raise ExecutionValidationError(
                    f"LabelExecutor requires a 'labels' list or legacy 'label'/'category' parameters. Found: {action.parameters}"
                )

        if not labels:
            raise ExecutionValidationError(
                f"LabelExecutor: No valid labels found to apply in parameters: {action.parameters}"
            )

        # Normalize label names: e.g. "PROJECT" -> "Category/Project"
        normalized_labels = []
        for l in labels:
            lbl = l.strip()
            if not lbl:
                continue
            if "/" not in lbl:
                normalized_val = lbl.replace("_", " ").strip().title()
                lbl = f"Category/{normalized_val}"
            normalized_labels.append(lbl)

        # 2. Dry-Run Handling
        if context.dry_run:
            logger.info("[DRY-RUN] Simulated creation/application of labels %s to email '%s'.", normalized_labels, email_id)
            first_label_name = normalized_labels[0] if normalized_labels else None
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.DRY_RUN,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={
                    "simulated_label": first_label_name,
                    "simulated_labels": normalized_labels,
                    "dry_run": True,
                },
            )

        # 3. Live Gmail API Execution
        service = context.client
        try:
            # 3.1 Get existing labels once, using execution context cache if available
            existing_labels = context.metadata.get("gmail_labels_cache")
            if existing_labels is None:
                labels_list = service.users().labels().list(userId="me").execute()
                existing_labels = labels_list.get("labels", [])
                context.metadata["gmail_labels_cache"] = existing_labels

            existing_label_map = {lbl["name"].lower(): lbl["id"] for lbl in existing_labels}

            label_ids = []
            applied_labels_meta = []

            for label_name in normalized_labels:
                label_id = existing_label_map.get(label_name.lower())

                # 3.2 Create label if missing
                if not label_id:
                    logger.info("Label '%s' not found. Creating label.", label_name)
                    label_body = {
                        "name": label_name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    }
                    created_label = service.users().labels().create(userId="me", body=label_body).execute()
                    label_id = created_label["id"]
                    # Update local map and context cache in case duplicates exist
                    existing_label_map[label_name.lower()] = label_id
                    existing_labels.append({"id": label_id, "name": label_name})
                    logger.info("Successfully created label '%s' with ID '%s'.", label_name, label_id)

                label_ids.append(label_id)
                applied_labels_meta.append({"name": label_name, "id": label_id})

            # 3.3 Apply labels to message in a single API call
            if label_ids:
                modify_body = {
                    "addLabelIds": label_ids,
                }
                service.users().messages().modify(userId="me", id=email_id, body=modify_body).execute()
                logger.info("Successfully applied labels %s to email '%s'.", normalized_labels, email_id)

            # Populate backwards-compatibility keys
            first_label_id = label_ids[0] if label_ids else None
            first_label_name = normalized_labels[0] if normalized_labels else None

            # Warn about legacy keys deprecation
            logger.warning(
                "Legacy provider_metadata fields 'label_id' and 'label_name' are deprecated. "
                "Please transition to using 'applied_labels: list[dict]'."
            )

            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SUCCESS,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata={
                    "label_name": first_label_name,
                    "label_id": first_label_id,
                    "applied_labels": applied_labels_meta,
                },
            )

        except HttpError as exc:
            logger.error("Gmail API error during label operations: %s", exc)
            raise ProviderAPIError(f"Gmail API failure during label execution: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in LabelExecutor: %s", exc)
            raise ProviderAPIError(f"Unexpected error in LabelExecutor: {exc}") from exc
