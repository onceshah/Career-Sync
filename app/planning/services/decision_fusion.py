"""
Decision Fusion Service.

Layer:
    Planning Layer (D1.5)

Responsibility:
    Reconciles deterministic PolicyDecision outputs with AI recommendations
    to produce a single authoritative ClassificationResult.

The Policy Engine is considered authoritative unless AI overrides are
explicitly permitted by the policy and requested by the AI.
"""

from __future__ import annotations

from typing import Any

from app.ai.models import AIDecision
from app.domain.enums import CategoryType, ActionType
from app.domain.models import (
    PolicyDecision,
    StructuredEmail,
    ActionDecision,
)

from app.planning.enums import ConflictResolutionStrategy
from app.planning.exceptions import PlanningValidationError
from app.planning.models import (
    ClassificationResult,
    DecisionAudit,
    FieldOverride,
)


class DecisionFusionService:
    """
    Reconciles deterministic policy decisions with AI recommendations.

    The service produces the authoritative business classification together
    with a complete audit trail describing how conflicts were resolved.
    """

    def fuse(
        self,
        email: StructuredEmail,
        policy: PolicyDecision,
        ai: AIDecision,
    ) -> tuple[ClassificationResult, DecisionAudit]:
        """
        Produce the final reconciled business classification.

        Returns
        -------
        tuple[ClassificationResult, DecisionAudit]
            The authoritative classification and reconciliation audit.
        """

        self._validate_inputs(email, policy, ai)

        overrides: list[FieldOverride] = []
        warnings: list[str] = []

        allow_override = (
            policy.is_override_allowed
            and ai.policy_overridden
        )

        folder = self._resolve_field(
            field_name="folder",
            policy_value=policy.folder,
            ai_value=ai.recommended_folder,
            allow_override=allow_override,
            overrides=overrides,
        )

        priority = self._resolve_field(
            field_name="priority",
            policy_value=policy.priority,
            ai_value=ai.priority,
            allow_override=allow_override,
            overrides=overrides,
        )

        vendor = self._resolve_field(
            field_name="vendor",
            policy_value=policy.vendor,
            ai_value=ai.vendor,
            allow_override=allow_override,
            overrides=overrides,
        )

        # Policy currently owns importance.
        importance = policy.importance

        categories = self._resolve_categories(
            policy=policy,
            ai=ai,
            overrides=overrides,
        )

        project = self._resolve_project(
            email=email,
            ai=ai,
            overrides=overrides,
        )

        actions = self._resolve_actions(
            policy=policy,
            ai=ai,
            allow_override=allow_override,
            overrides=overrides,
        )

        classification = self._build_classification(
            folder=folder,
            priority=priority,
            importance=importance,
            vendor=vendor,
            categories=categories,
            project=project,
            actions=actions,
        )

        audit = self._build_audit(
            overrides=overrides,
            warnings=warnings,
            allow_override=allow_override,
        )

        return classification, audit
    

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_inputs(
        email: StructuredEmail,
        policy: PolicyDecision,
        ai: AIDecision,
    ) -> None:
        """
        Validate the inputs required for decision fusion.
        """

        if email is None:
            raise PlanningValidationError(
                "StructuredEmail cannot be None."
            )

        if policy is None:
            raise PlanningValidationError(
                "PolicyDecision cannot be None."
            )

        if ai is None:
            raise PlanningValidationError(
                "AIDecision cannot be None."
            )

        if not ai.email_id:
            raise PlanningValidationError(
                "AI decision must contain an email identifier."
            )

        if policy.folder is None:
            raise PlanningValidationError(
                "Policy decision must contain a folder."
            )

        if policy.priority is None:
            raise PlanningValidationError(
                "Policy decision must contain a priority."
            )

        if not (0.0 <= ai.confidence <= 1.0):
            raise PlanningValidationError(
                "AI confidence must be between 0.0 and 1.0."
            )

        # Optional consistency check.
        if (
            email.headers is not None
            and email.headers.message_id
            and ai.email_id != email.headers.message_id
        ):
            # Future enhancement:
            # Record as warning instead of silently ignoring.
            pass

    # ------------------------------------------------------------------ #
    # Generic Resolution
    # ------------------------------------------------------------------ #

    def _resolve_field(
        self,
        *,
        field_name: str,
        policy_value: Any,
        ai_value: Any,
        allow_override: bool,
        overrides: list[FieldOverride],
    ) -> Any:
        """
        Resolve a single business field.

        Resolution order:

        1. Missing AI value -> Policy wins.
        2. Matching values -> Return either.
        3. Override allowed -> AI wins.
        4. Otherwise -> Policy wins.
        """

        if ai_value is None:
            return policy_value

        if policy_value == ai_value:
            return policy_value

        final_value = ai_value if allow_override else policy_value

        self._record_override(
            field_name=field_name,
            policy_value=policy_value,
            ai_value=ai_value,
            final_value=final_value,
            reason=(
                "AI override accepted."
                if allow_override
                else "Policy decision is authoritative."
            ),
            overrides=overrides,
        )

        return final_value

    # ------------------------------------------------------------------ #
    # Category Resolution
    # ------------------------------------------------------------------ #

    def _resolve_categories(
        self,
        *,
        policy: PolicyDecision,
        ai: AIDecision,
        overrides: list[FieldOverride],
    ) -> list[CategoryType]:
        """
        Merge policy and AI categories.

        Policy categories are always preserved.
        AI contributes additional categories only.
        """

        merged = list(policy.categories)

        for category in ai.categories:

            if category in merged:
                continue

            merged.append(category)

            self._record_override(
                field_name="categories",
                policy_value=policy.categories,
                ai_value=ai.categories,
                final_value=merged,
                reason=f"Added AI category '{category.value}'.",
                overrides=overrides,
            )

        return merged

    # ------------------------------------------------------------------ #
    # Project Resolution
    # ------------------------------------------------------------------ #

    def _resolve_project(
        self,
        *,
        email: StructuredEmail,
        ai: AIDecision,
        overrides: list[FieldOverride],
    ) -> str | None:
        """
        Resolve the project identifier.

        Existing project information extracted during ingestion is preserved.
        AI only enriches the result when no project already exists.
        """

        if email.project:
            return email.project

        project = ai.project.strip() if ai.project else None

        if not project:
            return None

        self._record_override(
            field_name="project",
            policy_value=email.project,
            ai_value=project,
            final_value=project,
            reason="Project populated from AI.",
            overrides=overrides,
        )

        return project
    

        # ------------------------------------------------------------------ #
    def _resolve_actions(
        self,
        *,
        policy: PolicyDecision,
        ai: AIDecision,
        allow_override: bool,
        overrides: list[FieldOverride],
    ) -> list[ActionDecision]:
        """
        Resolve the actions list.
        If override is allowed and AI has recommended actions, use them.
        Otherwise, default to policy actions.
        """
        if allow_override and ai.recommended_actions:
            ai_actions = []
            for rec in ai.recommended_actions:
                params = {}
                if rec.target:
                    if rec.action_type == ActionType.MOVE_TO_FOLDER:
                        params["folder"] = rec.target
                    elif rec.action_type == ActionType.ADD_CATEGORY:
                        params["labels"] = [rec.target]
                    else:
                        params["target"] = rec.target
                ai_actions.append(
                    ActionDecision(
                        action=rec.action_type,
                        parameters=params,
                    )
                )
            
            self._record_override(
                field_name="actions",
                policy_value=policy.actions,
                ai_value=ai_actions,
                final_value=ai_actions,
                reason="Actions overridden by AI recommendations.",
                overrides=overrides,
            )
            return ai_actions

        return list(policy.actions)

    # ------------------------------------------------------------------ #
    # Classification Builder
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_classification(
        *,
        folder,
        priority,
        importance,
        vendor,
        categories,
        project,
        actions,
    ) -> ClassificationResult:
        """
        Construct the immutable ClassificationResult.
        """

        return ClassificationResult(
            folder=folder,
            priority=priority,
            importance=importance,
            vendor=vendor,
            categories=categories,
            project=project,
            actions=actions,
        )

    # ------------------------------------------------------------------ #
    # Audit Builder
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_audit(
        *,
        overrides: list[FieldOverride],
        warnings: list[str],
        allow_override: bool,
    ) -> DecisionAudit:
        """
        Build the immutable decision audit record.
        """

        strategy = (
            ConflictResolutionStrategy.AI_AUTHORITATIVE
            if allow_override
            else ConflictResolutionStrategy.POLICY_AUTHORITATIVE
        )

        return DecisionAudit(
            strategy=strategy,
            conflicts_detected=bool(overrides),
            overrides=overrides,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    # Audit Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _record_override(
        *,
        field_name: str,
        policy_value: Any,
        ai_value: Any,
        final_value: Any,
        reason: str,
        overrides: list[FieldOverride],
    ) -> None:
        """
        Record a reconciliation decision.

        Values are converted to strings because FieldOverride currently stores
        string representations for audit purposes.
        """

        overrides.append(
            FieldOverride(
                field=field_name,
                policy_value=(
                    None
                    if policy_value is None
                    else str(policy_value)
                ),
                ai_value=(
                    None
                    if ai_value is None
                    else str(ai_value)
                ),
                final_value=(
                    None
                    if final_value is None
                    else str(final_value)
                ),
                reason=reason,
            )
        )