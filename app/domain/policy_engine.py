"""
Policy Engine evaluating StructuredEmail domain objects against business policy rules.

Layer: Domain Layer
Role: Evaluates input StructuredEmail models against loaded PolicyConfig rules
      and produces canonical PolicyDecision domain models.

Key design point
----------------
The engine MERGES every matched rule instead of taking the first match only.
The original first-match-wins implementation meant platform rules (which only
set ``vendor`` but appear first in the YAML) silently discarded the folder and
category decisions of more specific rules (rejection / interview / offer /
assessment) that matched the same email.
"""

import time
import logging
from collections import OrderedDict
from typing import List, Optional, Tuple

from app.domain.enums import (
    ActionType,
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
)
from app.domain.models import (
    ActionDecision,
    AuditInformation,
    PolicyDecision,
    ProcessingMetadata,
    StructuredEmail,
)
from app.domain.matching.condition_matcher import ConditionMatcher
from app.infrastructure.config.schema import PolicyConfig, PolicyRule
from app.infrastructure.config.loader import PolicyLoader

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Deterministic Policy Engine evaluating StructuredEmail domain objects against business policy rules.
    """

    def __init__(self, policy: Optional[PolicyConfig] = None):
        self.policy = policy or PolicyConfig()

    @classmethod
    def from_yaml_file(cls, yaml_filepath: str) -> "PolicyEngine":
        """Loads PolicyEngine from a YAML policy configuration file."""
        config = PolicyLoader.load_from_yaml(yaml_filepath)
        return cls(policy=config)

    def evaluate(self, email: StructuredEmail) -> PolicyDecision:
        """Evaluates a StructuredEmail against loaded policy rules to produce a PolicyDecision."""
        start_time = time.perf_counter()
        matched_rules: List[str] = []
        matched_rule_objs: List[PolicyRule] = []
        reasoning_list: List[str] = []

        for rule in self.policy.rules:
            if not rule.enabled:
                continue
            if ConditionMatcher.matches(rule.condition, email):
                matched_rules.append(rule.rule_id)
                matched_rule_objs.append(rule)
                reasoning_list.append(f"Matched rule '{rule.rule_id}' ({rule.name}).")
                logger.info(f"Email matched rule: {rule.rule_id} ({rule.name})")

        eval_time_ms = (time.perf_counter() - start_time) * 1000.0

        if not matched_rule_objs:
            audit = AuditInformation(
                matched_rules=[],
                reasoning=["No deterministic rules matched. Default routing applied."],
                policy_version=self.policy.version,
                evaluation_time_ms=eval_time_ms,
            )
            return PolicyDecision(
                folder=FolderType.LEADS,
                subfolder=None,
                categories=[CategoryType.JOB_OPPORTUNITY],
                vendor=email.vendor or VendorType.UNKNOWN,
                priority=PriorityLevel.NORMAL,
                importance=ImportanceLevel.NORMAL,
                flag=False,
                actions=self._build_actions(
                    folder=FolderType.LEADS,
                    categories=[CategoryType.JOB_OPPORTUNITY],
                    flag=False,
                ),
                is_override_allowed=True,
                audit=audit,
                metadata=ProcessingMetadata(
                    confidence=1.0,
                    processing_engine="RulePolicyEngine",
                ),
            )

        folder, subfolder, categories, vendor, priority, importance, flag, override_allowed, project = (
            self._merge_rules(matched_rule_objs, email)
        )

        audit = AuditInformation(
            matched_rules=matched_rules,
            reasoning=reasoning_list,
            policy_version=self.policy.version,
            evaluation_time_ms=eval_time_ms,
        )

        decision = PolicyDecision(
            folder=folder,
            subfolder=subfolder,
            categories=categories,
            vendor=vendor,
            priority=priority,
            importance=importance,
            flag=flag,
            actions=self._build_actions(folder, categories, flag),
            is_override_allowed=override_allowed,
            audit=audit,
            metadata=ProcessingMetadata(
                confidence=1.0,
                processing_engine="RulePolicyEngine",
            ),
        )
        return decision

    # ---------------------------------------------------------------------
    # Rule merging
    # ---------------------------------------------------------------------

    @staticmethod
    def _merge_rules(
        matched_rules: List[PolicyRule],
        email: StructuredEmail,
    ) -> Tuple[
        FolderType,
        Optional[str],
        List[CategoryType],
        VendorType,
        PriorityLevel,
        ImportanceLevel,
        bool,
        bool,
        Optional[str],
    ]:
        """
        Merges all matched rules into a single authoritative decision.

        Scalar fields (folder, subfolder, priority, importance, project) take the
        first non-None value in YAML order, so more specific rules later in the
        file override the generic platform rules. Categories are unioned across all
        matched rules, ``flag`` is OR-ed, and ``is_override_allowed`` is AND-ed
        (any lock disables downstream AI override for this email).
        """
        folder = None
        subfolder = None
        priority = None
        importance = None
        project = None
        categories: "OrderedDict[CategoryType, None]" = OrderedDict()
        flag = False
        override_allowed = True
        vendor = None

        for rule in matched_rules:
            act = rule.action
            if act.folder is not None and folder is None:
                folder = act.folder
            if act.subfolder is not None and subfolder is None:
                subfolder = act.subfolder
            if act.priority is not None and priority is None:
                priority = act.priority
            if act.importance is not None and importance is None:
                importance = act.importance
            if act.project is not None and project is None:
                project = act.project
            if act.vendor is not None and vendor is None:
                vendor = act.vendor
            for cat in act.categories:
                categories[cat] = None
            flag = flag or act.flag
            override_allowed = override_allowed and act.is_override_allowed

        final_folder = folder or FolderType.LEADS
        final_categories = list(categories.keys()) or [CategoryType.JOB_OPPORTUNITY]
        final_vendor = vendor or email.vendor or VendorType.UNKNOWN
        final_priority = priority or PriorityLevel.NORMAL
        final_importance = importance or ImportanceLevel.NORMAL

        return (
            final_folder,
            subfolder,
            final_categories,
            final_vendor,
            final_priority,
            final_importance,
            flag,
            override_allowed,
            project,
        )

    @staticmethod
    def _build_actions(
        folder: FolderType,
        categories: List[CategoryType],
        flag: bool,
    ) -> List[ActionDecision]:
        """Builds the executable action set for a merged PolicyDecision."""
        actions: List[ActionDecision] = []
        if folder:
            actions.append(
                ActionDecision(
                    action=ActionType.MOVE_TO_FOLDER,
                    parameters={"folder": folder.value},
                )
            )
        for cat in categories:
            actions.append(
                ActionDecision(
                    action=ActionType.ADD_CATEGORY,
                    parameters={"labels": [cat.value]},
                )
            )
        if flag:
            actions.append(
                ActionDecision(
                    action=ActionType.FLAG_FOR_REVIEW,
                    parameters={"reason": "Priority communication flagged for human review."},
                )
            )
        return actions