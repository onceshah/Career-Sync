"""
Outlook Execution Provider.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.domain.enums import ActionType
from app.planning.models import PlannedAction
from app.execution.exceptions import ExecutionValidationError
from app.execution.interfaces import ExecutionProvider
from app.execution.models import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ExecutionContext,
)
from app.execution.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class OutlookExecutionProvider(ExecutionProvider):
    """
    Outlook implementation of ExecutionProvider acting as a dispatcher for Outlook actions.
    This provider is pending full Microsoft Graph API authentication.
    """

    def execute_action(
        self,
        action: PlannedAction,
        email_id: str,
        context: ExecutionContext,
    ) -> ActionExecutionResult:
        """
        Executes a single planned action against Microsoft Outlook/Graph.

        Parameters
        ----------
        action : PlannedAction
            The planned action containing the ActionType and parameters.
        email_id : str
            Identifier of the email target.
        context : ExecutionContext
            The execution-scoped context carrying client dependencies and configuration.

        Returns
        -------
        ActionExecutionResult
            The outcome of executing this specific action.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "Outlook provider processing action '%s' for email '%s' (dry_run: %s).",
            action.action,
            email_id,
            context.dry_run,
        )

        # 1. Parameter Validation
        if not email_id or not isinstance(email_id, str):
            raise ExecutionValidationError("Outlook provider requires a non-empty string email_id.")

        # Validate Action Parameters
        if action.action == ActionType.ADD_CATEGORY:
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
                else:
                    raise ExecutionValidationError(
                        f"Outlook ADD_CATEGORY action requires a 'labels' list or legacy 'label'/'category' parameters. Found: {action.parameters}"
                    )
            if not labels:
                raise ExecutionValidationError(
                    f"Outlook ADD_CATEGORY action: No valid categories found to apply in parameters: {action.parameters}"
                )

        elif action.action == ActionType.MOVE_TO_FOLDER:
            folder_path = action.parameters.get("folder")
            if not folder_path:
                raise ExecutionValidationError(
                    f"Outlook MOVE_TO_FOLDER action requires a 'folder' parameter. Found: {action.parameters}"
                )

        elif action.action not in (
            ActionType.FLAG_FOR_REVIEW,
            ActionType.ESCALATE,
            ActionType.ARCHIVE,
            ActionType.IGNORE,
        ):
            logger.warning("Action type '%s' is not supported by the Outlook provider.", action.action)
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.SKIPPED,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                error_message=f"Action type '{action.action}' is not supported by the Outlook provider.",
            )

        # 2. Dry-Run simulated handling
        if context.dry_run:
            logger.info("[DRY-RUN] Simulated Outlook execution for action '%s' on email '%s'.", action.action, email_id)
            
            provider_metadata = {"dry_run": True}
            if action.action == ActionType.ADD_CATEGORY:
                # Re-extract clean labels for simulated metadata
                labels_val = action.parameters.get("labels")
                if labels_val is not None:
                    labels = [str(l) for l in labels_val if l] if isinstance(labels_val, list) else [str(labels_val)]
                else:
                    labels = [str(action.parameters.get("label") or action.parameters.get("category"))]
                provider_metadata["simulated_categories"] = labels
            elif action.action == ActionType.MOVE_TO_FOLDER:
                provider_metadata["simulated_folder"] = str(action.parameters.get("folder"))
            elif action.action == ActionType.ESCALATE:
                provider_metadata["simulated_flag"] = "Escalated"
            elif action.action == ActionType.FLAG_FOR_REVIEW:
                provider_metadata["simulated_flag"] = "Flagged"
            elif action.action == ActionType.ARCHIVE:
                provider_metadata["simulated_archive"] = True
            elif action.action == ActionType.IGNORE:
                provider_metadata["simulated_ignore"] = True
            
            return ActionExecutionResult(
                action_type=action.action,
                status=ActionExecutionStatus.DRY_RUN,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0,
                provider_metadata=provider_metadata,
            )

        # 3. Live Microsoft Graph API Access requires Authentication
        raise NotImplementedError(
            "Microsoft Graph authentication is not implemented. This provider is intended to be integrated with the organization's authentication layer."
        )


# Auto-register Outlook execution provider
ProviderRegistry.register("outlook", OutlookExecutionProvider)
