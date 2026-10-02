"""
Enterprise Action Planning Service.

Responsible for translating ClassificationResult, FolderPlan, and LabelPlan
into a provider-independent ActionPlan.
"""

from __future__ import annotations

from app.domain.enums import ActionType
from app.planning.constants import ACTION_ORDER
from app.planning.models import (
    ActionPlan,
    ClassificationResult,
    FolderPlan,
    LabelPlan,
    PlannedAction,
)


class ActionPlanningService:
    """
    Translates planning artefacts into a canonical ActionPlan.

    This service is responsible only for deciding WHAT business
    actions should be executed. The Execution Layer is responsible
    for translating these actions into provider-specific API calls.
    """

    def build_plan(
        self,
        classification: ClassificationResult,
        folder_plan: FolderPlan,
        label_plan: LabelPlan,
    ) -> ActionPlan:
        """
        Build a provider-independent ActionPlan.
        """

        actions: list[PlannedAction] = []

        #
        # Folder actions
        #

        if (
            folder_plan.full_path
            and folder_plan.full_path != "INBOX"
        ):
            actions.append(
                PlannedAction(
                    action=ActionType.MOVE_TO_FOLDER,
                    parameters={
                        "folder": folder_plan.full_path,
                    },
                )
            )

        #
        # Label actions
        #

        if label_plan.labels_to_apply:
            actions.append(
                PlannedAction(
                    action=ActionType.ADD_CATEGORY,
                    parameters={
                        "labels": list(
                            label_plan.labels_to_apply
                        ),
                    },
                )
            )

        #
        # Preserve policy / AI actions determined during
        # Decision Fusion.
        #

        for action in classification.actions:
            actions.append(
                PlannedAction(
                    action=action.action,
                    parameters=dict(action.parameters),
                )
            )

        actions = self._normalize_actions(actions, folder_plan)

        actions = self._deduplicate(actions)

        actions = self._order_steps(actions)

        self._validate(actions)

        return ActionPlan(actions=actions)

    @staticmethod
    def _normalize_actions(
        actions: list[PlannedAction],
        folder_plan: FolderPlan,
    ) -> list[PlannedAction]:
        """
        Normalize and consolidate actions:
        1. Merges all ADD_CATEGORY actions into a single action with the union of all labels.
        2. Uses FolderPlan.full_path as the sole authoritative folder action if set,
           otherwise discards all folder actions.
        """
        category_labels = []
        other_actions = []

        for action in actions:
            if action.action == ActionType.ADD_CATEGORY:
                labels_val = action.parameters.get("labels")
                if isinstance(labels_val, list):
                    category_labels.extend(labels_val)
                elif labels_val:
                    category_labels.append(labels_val)
                # Fallbacks for legacy single-string params
                elif action.parameters.get("category"):
                    category_labels.append(action.parameters.get("category"))
                elif action.parameters.get("label"):
                    category_labels.append(action.parameters.get("label"))

            elif action.action != ActionType.MOVE_TO_FOLDER:
                other_actions.append(action)

        normalized: list[PlannedAction] = []

        # 1. Consolidate ADD_CATEGORY actions
        if category_labels:
            # Deduplicate labels while preserving order
            unique_labels = []
            for label in category_labels:
                if label not in unique_labels:
                    unique_labels.append(label)
            normalized.append(
                PlannedAction(
                    action=ActionType.ADD_CATEGORY,
                    parameters={"labels": unique_labels},
                )
            )

        # 2. Establish FolderPlan.full_path as the sole authoritative folder action
        if folder_plan.full_path and folder_plan.full_path != "INBOX":
            normalized.append(
                PlannedAction(
                    action=ActionType.MOVE_TO_FOLDER,
                    parameters={"folder": folder_plan.full_path},
                )
            )

        # 3. Re-add other actions (e.g. FLAG_FOR_REVIEW, ARCHIVE, etc.)
        normalized.extend(other_actions)

        return normalized

    @staticmethod
    def _order_steps(
        steps: list[PlannedAction],
    ) -> list[PlannedAction]:
        """
        Return planned actions in deterministic order.
        """

        return sorted(
            steps,
            key=lambda step: ACTION_ORDER.get(
                step.action,
                99,
            ),
        )

    @staticmethod
    def _deduplicate(
        actions: list[PlannedAction],
    ) -> list[PlannedAction]:
        """
        Remove duplicate planned actions while preserving order.
        """

        unique: list[PlannedAction] = []

        for action in actions:
            if action not in unique:
                unique.append(action)

        return unique

    @staticmethod
    def _validate(
        actions: list[PlannedAction],
    ) -> None:
        """
        Validate the generated ActionPlan.
        """

        for action in actions:

            if (
                action.action
                == ActionType.MOVE_TO_FOLDER
            ):
                if (
                    "folder"
                    not in action.parameters
                    or not action.parameters["folder"]
                ):
                    raise ValueError(
                        "MOVE_TO_FOLDER requires a destination folder."
                    )

            elif (
                action.action
                == ActionType.ADD_CATEGORY
            ):
                if (
                    "labels"
                    not in action.parameters
                    or not action.parameters["labels"]
                ):
                    raise ValueError(
                        "ADD_CATEGORY requires labels."
                    )