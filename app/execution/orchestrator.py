"""
ExecutionOrchestrator implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.planning.models import ExecutionPlan
from app.execution.exceptions import ExecutionValidationError
from app.execution.interfaces import ExecutionProvider
from app.execution.models import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    Orchestrates the execution of a provider-independent ExecutionPlan.
    """

    def __init__(self, provider: ExecutionProvider | None = None) -> None:
        """
        Initializes the orchestrator with an optional default provider.
        """
        self._provider = provider

    def execute(
        self,
        plan: ExecutionPlan,
        client: Any = None,
        context: ExecutionContext | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
        provider_name: str = "gmail",
    ) -> ExecutionResult:
        """
        Executes the actions specified in the ExecutionPlan.

        Parameters
        ----------
        plan : ExecutionPlan
            The plan containing actions to run.
        client : Any, optional
            The raw provider client (if not supplying a pre-built context).
        context : ExecutionContext, optional
            A pre-configured ExecutionContext.
        dry_run : bool, default False
            If True, runs in simulated dry-run mode.
        session_id : str, optional
            Optional identifier for transaction tracking.
        provider_name : str, default "gmail"
            The registered provider to use.

        Returns
        -------
        ExecutionResult
            The aggregated execution outcome.
        """
        start_time = datetime.now(timezone.utc)
        # 1. Precondition and Input Validation
        self._validate_preconditions(plan, client, context)

        email_id = plan.email.email_id
        logger.info(
            "Starting execution of plan for email '%s' (session: %s, dry-run: %s).",
            email_id,
            session_id,
            dry_run,
        )

        # 2. Establish ExecutionContext
        if context is None:
            context = ExecutionContext(
                client=client,
                dry_run=dry_run,
                session_id=session_id,
            )

        # 3. Resolve ExecutionProvider
        provider = self._resolve_provider(provider_name)

        # 4. Iterate and Execute PlannedActions
        action_results: list[ActionExecutionResult] = []
        actions = plan.action_plan.actions

        for action in actions:
            action_start = datetime.now(timezone.utc)
            logger.info("Executing action '%s' for email '%s'.", action.action, plan.email.email_id)

            try:
                result = provider.execute_action(
                    action=action,
                    email_id=plan.email.email_id,
                    context=context,
                )
            except Exception as exc:
                action_end = datetime.now(timezone.utc)
                duration = (action_end - action_start).total_seconds() * 1000.0
                logger.exception("Failed to execute action '%s': %s", action.action, exc)
                result = ActionExecutionResult(
                    action_type=action.action,
                    status=ActionExecutionStatus.FAILED,
                    started_at=action_start,
                    completed_at=action_end,
                    duration_ms=duration,
                    error_message=str(exc),
                )

            action_results.append(result)

        # 5. Aggregate Execution Status
        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000.0
        status = self._aggregate_status(action_results, context.dry_run)

        logger.info(
            "Completed execution of plan for email '%s' | Status=%s | Duration=%.2fms",
            plan.email.email_id,
            status.value,
            duration_ms,
        )

        return ExecutionResult(
            email_id=plan.email.email_id,
            status=status,
            started_at=start_time,
            completed_at=end_time,
            duration_ms=duration_ms,
            actions=action_results,
            dry_run=context.dry_run,
        )

    def _validate_preconditions(
        self,
        plan: ExecutionPlan,
        client: Any,
        context: ExecutionContext | None,
    ) -> None:
        """
        Validates basic invariants before starting execution.
        """
        if not plan:
            raise ExecutionValidationError("ExecutionPlan cannot be None.")

        if not plan.email or not plan.email.email_id:
            raise ExecutionValidationError("ExecutionPlan must contain a valid EmailReference and email_id.")

        if context is None and client is None:
            raise ExecutionValidationError(
                "preconditions failed: Either client or context must be provided."
            )

    def _resolve_provider(self, provider_name: str) -> ExecutionProvider:
        """
        Resolves the provider by name, preferring the injected provider.
        """
        if self._provider:
            return self._provider

        from app.execution.providers.registry import ProviderRegistry

        return ProviderRegistry.get_provider(provider_name)

    @staticmethod
    def _aggregate_status(
        results: list[ActionExecutionResult],
        dry_run: bool,
    ) -> ExecutionStatus:
        """
        Aggregates individual action statuses into an overall ExecutionStatus.
        """
        if not results:
            return ExecutionStatus.DRY_RUN if dry_run else ExecutionStatus.SUCCESS

        successes = sum(1 for r in results if r.status in (ActionExecutionStatus.SUCCESS, ActionExecutionStatus.DRY_RUN))
        failures = sum(1 for r in results if r.status == ActionExecutionStatus.FAILED)

        if failures == 0:
            return ExecutionStatus.DRY_RUN if dry_run else ExecutionStatus.SUCCESS
        elif successes == 0:
            return ExecutionStatus.FAILED
        else:
            return ExecutionStatus.PARTIAL_SUCCESS
