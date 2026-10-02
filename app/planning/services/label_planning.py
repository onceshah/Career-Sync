"""
Enterprise Label Planning Service.

Responsible for generating provider-independent labels from the
final ClassificationResult produced by the Decision Fusion stage.

This service is configuration-driven and relies on the enterprise
taxonomy rather than hardcoded business values.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from app.infrastructure.config.schema import TaxonomyConfig
from app.planning.models import (
    ClassificationResult,
    LabelPlan,
)


class LabelPlanningService:
    """
    Builds enterprise labels from a ClassificationResult.

    Responsibilities
    ----------------
    - Generate provider-independent labels
    - Use enterprise taxonomy
    - Produce LabelPlan

    Does NOT:
    - Make AI decisions
    - Execute actions
    - Modify classifications
    """

    def __init__(self, taxonomy: TaxonomyConfig):
        self._taxonomy = taxonomy

    def build_plan(
        self,
        classification: ClassificationResult,
    ) -> LabelPlan:
        """
        Generate labels from a classification result.
        """

        labels: list[str] = []

        priority = self._generate_priority_label(
            classification.priority
        )

        importance = self._generate_importance_label(
            classification.importance
        )

        if priority:
            labels.append(priority)

        if importance:
            labels.append(importance)

        labels = self._deduplicate(labels)

        self._validate(labels)

        return LabelPlan(
            labels_to_create=list(labels),
            labels_to_apply=list(labels),
        )

    # ------------------------------------------------------------------
    # Label Generators
    # ------------------------------------------------------------------

    def _generate_priority_label(
        self,
        priority,
    ) -> Optional[str]:

        return self._generate_label(
            prefix=self._taxonomy.label_prefixes.priority,
            value=priority,
        )

    def _generate_importance_label(
        self,
        importance,
    ) -> Optional[str]:

        return self._generate_label(
            prefix=self._taxonomy.label_prefixes.importance,
            value=importance,
        )

    # ------------------------------------------------------------------
    # Generic Helpers
    # ------------------------------------------------------------------

    def _generate_label(
        self,
        prefix: str,
        value: Enum | str | None,
    ) -> Optional[str]:
        """
        Converts an enum/string into a normalized enterprise label.
        """

        if value is None:
            return None

        if isinstance(value, Enum):
            value = value.value

        return self._build_label(prefix, str(value))

    def _build_label(
        self,
        prefix: str,
        value: str,
    ) -> str:
        """
        Builds a normalized enterprise label.

        Example
        -------
        Priority + HIGH

        →

        Priority/High
        """

        normalized = (
            value
            .replace("_", " ")
            .strip()
            .title()
        )

        return f"{prefix}/{normalized}"

    # ------------------------------------------------------------------
    # Validation Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate(
        labels: list[str],
    ) -> list[str]:
        """
        Remove duplicate labels while preserving insertion order.
        """

        seen: set[str] = set()
        unique: list[str] = []

        for label in labels:

            if label in seen:
                continue

            seen.add(label)
            unique.append(label)

        return unique

    @staticmethod
    def _validate(
        labels: list[str],
    ) -> None:
        """
        Validate generated enterprise labels.
        """

        for label in labels:

            if label is None:
                raise ValueError(
                    "Label cannot be None."
                )

            if not label.strip():
                raise ValueError(
                    "Label cannot be empty."
                )

            if "/" not in label:
                raise ValueError(
                    f"Invalid label format: {label}"
                )

            prefix, value = label.split("/", 1)

            if not prefix.strip():
                raise ValueError(
                    f"Invalid label prefix: {label}"
                )

            if not value.strip():
                raise ValueError(
                    f"Invalid label value: {label}"
                )