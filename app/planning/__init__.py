"""
Enterprise Classification, Labeling & Action Planning Engine (D1.5).

This package provides the provider-independent planning layer responsible for
transforming deterministic policy decisions and AI-assisted classifications
into executable planning contracts.

Public API
----------
Models
    ExecutionPlan
    EmailReference
    ClassificationResult
    FolderPlan
    LabelPlan
    PlannedAction
    ActionPlan
    PlanningMetadata

Enums
    PlanningStatus
    ConflictResolutionStrategy

Interfaces
    PlanningService
"""

# ============================================================================
# Enums
# ============================================================================

from .enums import (
    ConflictResolutionStrategy,
    PlanningStatus,
)

# ============================================================================
# Models
# ============================================================================

from .models import (
    ActionPlan,
    ClassificationResult,
    EmailReference,
    ExecutionPlan,
    FolderPlan,
    LabelPlan,
    PlannedAction,
    PlanningMetadata,
)



# ============================================================================
# Interfaces
# ============================================================================

from .interfaces import PlanningService


__all__ = [
    # Enums
    "PlanningStatus",
    "ConflictResolutionStrategy",

    # Models
    "EmailReference",
    "ClassificationResult",
    "FolderPlan",
    "LabelPlan",
    "PlannedAction",
    "ActionPlan",
    "PlanningMetadata",
    "ExecutionPlan",

    # Interfaces
    "PlanningService",
]


#Exceptions
from .exceptions import (
    PlanningError,
    PlanningValidationError,
    DecisionFusionError,
    ConflictResolutionError,
    LabelPlanningError,
    FolderPlanningError,
    ActionPlanningError,
)