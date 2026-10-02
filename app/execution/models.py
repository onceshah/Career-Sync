"""
Execution layer models and result contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ActionType


class ExecutionStatus(str, Enum):
    """
    Indicates the overall execution result of an ExecutionPlan.
    """

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    DRY_RUN = "DRY_RUN"


class ActionExecutionStatus(str, Enum):
    """
    Indicates the result of executing an individual PlannedAction.
    """

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DRY_RUN = "DRY_RUN"


class ExecutionContext(BaseModel):
    """
    Carries execution-scoped dependencies, parameters, and transaction-like context.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Any = Field(
        description="The provider-specific API client (e.g. Gmail resource client)."
    )
    dry_run: bool = Field(
        default=False,
        description="Whether to run the execution in a simulated dry-run mode."
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session or transaction identifier for tracing."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom metadata scoped to this execution run."
    )


class ActionExecutionResult(BaseModel):
    """
    Stable execution contract for a single PlannedAction.
    """

    model_config = ConfigDict(frozen=True)

    action_type: ActionType
    status: ActionExecutionStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    error_message: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """
    Stable aggregated execution contract for an entire ExecutionPlan.
    """

    model_config = ConfigDict(frozen=True)

    email_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    actions: list[ActionExecutionResult] = Field(default_factory=list)
    dry_run: bool = False
    ats_summary: dict[str, Any] | None = Field(
        default=None,
        description="Optional ATS synchronisation summary produced by the D6 CareerSyncEngine.",
    )
