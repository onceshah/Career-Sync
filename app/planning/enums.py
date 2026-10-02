"""
Planning-specific enumerations.

This module defines enumerations that are unique to the Enterprise
Classification, Labeling & Action Planning Engine (D1.5).

Business concepts such as folders, priorities, categories, vendors,
importance levels, and actions are intentionally reused from
``app.domain.enums`` to maintain a single canonical vocabulary across
the system.

Only planning-specific lifecycle and orchestration concepts belong here.
"""

from __future__ import annotations

from enum import Enum


class PlanningStatus(str, Enum):
    """
    Represents the overall status of execution plan generation.

    This status reflects whether the planning engine successfully produced
    a valid provider-independent execution plan.
    """

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ConflictResolutionStrategy(str, Enum):
    """
    Describes how conflicts between deterministic policy decisions and
    AI recommendations were resolved.

    These values are intended for auditing and explainability rather than
    controlling business logic directly.
    """

    POLICY_AUTHORITATIVE = "POLICY_AUTHORITATIVE"
    AI_AUTHORITATIVE = "AI_AUTHORITATIVE"
    MERGED = "MERGED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"



#MOVE TO ACTION PLANNER
class ActionExecutionOrder(int, Enum):
    """
    Defines the canonical execution order for provider-independent actions.

    Execution layers should sort planned actions using this ordering to
    ensure deterministic behaviour regardless of the underlying email
    provider implementation.

    Typical execution flow:

        1. Create labels
        2. Apply labels
        3. Move email
        4. Mark importance
        5. Flag email
        6. Archive email
    """

    CREATE_LABEL = 10
    APPLY_LABEL = 20
    MOVE_EMAIL = 30
    MARK_IMPORTANCE = 40
    FLAG_EMAIL = 50
    ARCHIVE_EMAIL = 60