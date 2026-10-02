"""
Enterprise Planning Orchestrator.

Combines decision fusion, folder planning, label planning, and action planning
to construct the final ExecutionPlan.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.ai.models import AIDecision
from app.domain.models import PolicyDecision, StructuredEmail
from app.infrastructure.config.schema import TaxonomyConfig

from .interfaces import PlanningService
from .models import (
    EmailReference,
    ExecutionPlan,
    PlanningMetadata,
    PlanningStatus,
)
from .services.action_planning import ActionPlanningService
from .services.decision_fusion import DecisionFusionService
from .services.folder_planning import FolderPlanningService
from .services.label_planning import LabelPlanningService


class PlanningOrchestrator(PlanningService):
    """
    Orchestrates the creation of provider-independent execution plans.
    """

    def __init__(self, taxonomy: TaxonomyConfig) -> None:
        self.fusion_service = DecisionFusionService()
        self.folder_planner = FolderPlanningService(taxonomy)
        self.label_planner = LabelPlanningService(taxonomy)
        self.action_planner = ActionPlanningService()

    def plan(
        self,
        email: StructuredEmail,
        policy: PolicyDecision,
        ai: AIDecision,
    ) -> ExecutionPlan:
        """
        Orchestrate decision fusion and planning services to build an ExecutionPlan.
        """
        # 1. Reconcile Policy and AI classifications
        classification, audit = self.fusion_service.fuse(email, policy, ai)

        # 2. Build logical labels
        label_plan = self.label_planner.build_plan(classification)

        # 3. Determine destination folder path
        folder_plan = self.folder_planner.build_plan(classification, label_plan)

        # 4. Generate discrete actions
        action_plan = self.action_planner.build_plan(
            classification,
            folder_plan,
            label_plan,
        )

        # 5. Build metadata
        metadata = PlanningMetadata(
            status=PlanningStatus.COMPLETED,
            generated_at=datetime.now(timezone.utc),
            planner_version="1.5.0",
            decision_audit=audit,
        )

        # 6. Build email reference
        email_ref = EmailReference(
            email_id=email.headers.message_id if email.headers and email.headers.message_id else "UNKNOWN_ID",
            message_id=email.headers.message_id if email.headers and email.headers.message_id else "",
            thread_id=email.headers.references[0] if email.headers and email.headers.references else None,
        )

        return ExecutionPlan(
            email=email_ref,
            classification=classification,
            folder_plan=folder_plan,
            label_plan=label_plan,
            action_plan=action_plan,
            metadata=metadata,
        )
