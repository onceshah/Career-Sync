"""
Planning service interfaces.

This module defines the public contracts for the Enterprise Classification,
Labeling & Action Planning Engine (D1.5).

Only the PlanningService interface is exposed to external modules.

Implementation details such as decision fusion, label generation, folder
planning, and action planning remain internal to the planning package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import AIDecision
from app.domain.models import (
    PolicyDecision,
    StructuredEmail,
)

from .models import ExecutionPlan


class PlanningService(ABC):
    """
    Public contract for the D1.5 Planning Engine.

    Implementations transform deterministic policy decisions and AI-assisted
    classifications into a provider-independent ExecutionPlan.

    Responsibilities
    ----------------
    - Reconcile policy and AI decisions
    - Generate classification results
    - Produce folder plans
    - Produce label plans
    - Produce action plans
    - Return a complete ExecutionPlan

    Non-Responsibilities
    --------------------
    - Execute provider actions
    - Call AI models
    - Evaluate policy rules
    - Persist execution plans
    - Expose HTTP endpoints
    """

    @abstractmethod
    def plan(
        self,
        email: StructuredEmail,
        policy: PolicyDecision,
        ai: AIDecision,
    ) -> ExecutionPlan:
        """
        Produce a provider-independent execution plan.

        Parameters
        ----------
        email:
            Canonical email representation.

        policy:
            Deterministic policy engine output.

        ai:
            AI-assisted decision.

        Returns
        -------
        ExecutionPlan
            Fully validated execution blueprint.
        """
        raise NotImplementedError