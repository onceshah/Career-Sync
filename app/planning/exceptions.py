"""
Planning engine exceptions.

This module defines the exception hierarchy for the Enterprise
Classification, Labeling & Action Planning Engine (D1.5).

All planning-related exceptions should inherit from PlanningError.
This allows callers to catch a single base exception while still
supporting more granular error handling where required.
"""

from __future__ import annotations


class PlanningError(Exception):
    """
    Base exception for all planning engine failures.
    """

    pass


class PlanningValidationError(PlanningError):
    """
    Raised when an invalid or incomplete execution plan is produced.

    Examples
    --------
    - Missing folder destination.
    - Invalid action sequence.
    - Required planning data is absent.
    """

    pass


class DecisionFusionError(PlanningError):
    """
    Raised when deterministic policy decisions and AI recommendations
    cannot be reconciled into a valid business decision.
    """

    pass


class ConflictResolutionError(DecisionFusionError):
    """
    Raised when a decision conflict cannot be resolved according to the
    configured conflict resolution strategy.
    """

    pass


class LabelPlanningError(PlanningError):
    """
    Raised when label generation or validation fails.
    """

    pass


class FolderPlanningError(PlanningError):
    """
    Raised when a valid destination folder cannot be determined.
    """

    pass


class ActionPlanningError(PlanningError):
    """
    Raised when an invalid or inconsistent action plan is generated.

    Examples
    --------
    - Unsupported action combination.
    - Duplicate mandatory actions.
    - Invalid execution ordering.
    """

    pass