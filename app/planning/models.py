"""
Planning domain models.

This module defines the canonical data contracts for the Enterprise
Classification, Labeling & Action Planning Engine (D1.5).

The aggregate root of this module is ``ExecutionPlan``. It represents the
provider-independent execution blueprint produced after deterministic policy
evaluation (D0) and AI-assisted decision validation (D1).

These models intentionally contain planning intent only. They must not contain
provider-specific implementation details such as Gmail label IDs, Outlook
folder identifiers, HTTP responses, or persistence metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


from app.domain.enums import (
    ActionType,
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
)

from .enums import (
    ConflictResolutionStrategy,
    PlanningStatus,
)


# ============================================================================
# Value Objects
# ============================================================================

class EmailReference(BaseModel):
    """
    Immutable reference to the email being planned.
    """

    model_config = ConfigDict(frozen=True)

    email_id: str
    message_id: str
    thread_id: str | None = None


from app.domain.models import ActionDecision

class ClassificationResult(BaseModel):
    """
    Final business classification after deterministic policy evaluation
    and AI validation have been reconciled.
    """

    model_config = ConfigDict(frozen=True)

    folder: FolderType
    priority: PriorityLevel
    importance: ImportanceLevel

    vendor: VendorType | None = None

    categories: list[CategoryType] = Field(default_factory=list)

    project: str | None = None

    actions: list[ActionDecision] = Field(default_factory=list)



class FolderPlan(BaseModel):
    """
    Provider-independent folder placement plan.
    """

    folder_type: FolderType

    folder: str

    subfolder: str | None = None

    full_path: str

    exists_in_taxonomy: bool = True


class LabelPlan(BaseModel):
    """
    Describes label operations required by the execution layer.
    """

    model_config = ConfigDict(frozen=True)

    labels_to_create: list[str] = Field(default_factory=list)

    labels_to_apply: list[str] = Field(default_factory=list)


class PlannedAction(BaseModel):
    """
    A single provider-independent action to be executed.
    """

    model_config = ConfigDict(frozen=True)

    action: ActionType

    parameters: dict[str, Any] = Field(default_factory=dict)


class ActionPlan(BaseModel):
    """
    Ordered collection of execution actions.
    """

    model_config = ConfigDict(frozen=True)

    actions: list[PlannedAction] = Field(default_factory=list)


class PlanningMetadata(BaseModel):
    """
    Metadata describing how the execution plan was generated.
    """

    model_config = ConfigDict(frozen=True)

    status: PlanningStatus

    generated_at: datetime

    planner_version: str

    decision_audit: DecisionAudit

    #planning_id: UUID



# ============================================================================
# Aggregate Root
# ============================================================================

class ExecutionPlan(BaseModel):
    """
    Aggregate root representing the complete provider-independent
    execution blueprint for an email.

    This object is the canonical output of the D1.5 Planning Engine and
    serves as the contract for downstream modules including:

    - D1.6 Execution Layer
    - D2 Persistence
    - D3 FastAPI
    - D4 Dashboard
    """

    model_config = ConfigDict(frozen=True)

    email: EmailReference

    classification: ClassificationResult

    folder_plan: FolderPlan

    label_plan: LabelPlan

    action_plan: ActionPlan

    metadata: PlanningMetadata




class FieldOverride(BaseModel):
    """
    Represents a single field reconciliation performed during
    decision fusion.
    """

    model_config = ConfigDict(frozen=True)

    field: str

    policy_value: str | None = None

    ai_value: str | None = None

    final_value: str | None = None

    reason: str


class DecisionAudit(BaseModel):
    """
    Captures how policy and AI decisions were reconciled.

    This model exists for explainability, auditing, and future
    dashboard visualisation.
    """

    model_config = ConfigDict(frozen=True)

    strategy: ConflictResolutionStrategy

    conflicts_detected: bool = False

    overrides: list[FieldOverride] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)




class ActionStep(BaseModel):
    """
    A single provider-independent execution action.

    The execution layer is responsible for translating these
    business actions into Gmail, Outlook, or any future provider's
    API operations.
    """

    action: ActionType = Field(
        description="Business action to execute."
    )

    resource: str | None = Field(
        default=None,
        description=(
            "Target resource associated with the action, "
            "such as a label name, folder path, or "
            "importance level."
        ),
    )

