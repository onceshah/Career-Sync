"""
Policy rules configuration schema models for loading and validating YAML policy files.

Layer: Infrastructure Layer
Role: Defines Pydantic models for parsing and validating YAML policy files
      into strongly-typed PolicyConfig domain objects.

Interacting Components:
    - app.domain.enums (FolderType, CategoryType, PriorityLevel, ImportanceLevel, VendorType)
    - app.infrastructure.config.loader (PolicyLoader)
    - app.domain.policy_engine (PolicyEngine)
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
)


class RuleCondition(BaseModel):
    """
    Matching criteria evaluated against a StructuredEmail.

    Responsibility:
        Defines optional filter parameters parsed from YAML policy rule conditions.

    Inputs:
        subject_contains, body_contains, sender_domain, recipient_domain,
        sender_email, recipient_email, cc_email, project, vendor, intent,
        only_cc, has_attachment.

    Outputs:
        RuleCondition schema object.

    Role within Architecture:
        Infrastructure schema model used by PolicyRule.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    subject_contains: Optional[List[str]] = Field(
        default=None,
        description="Match if the subject contains any of these values.",
    )

    body_contains: Optional[List[str]] = Field(
        default=None,
        description="Match if the body contains any of these values.",
    )

    sender_domain: Optional[List[str]] = Field(
        default=None,
        description="Match sender email domain.",
    )

    recipient_domain: Optional[List[str]] = Field(
        default=None,
        description="Match recipient email domain.",
    )

    sender_email: Optional[List[str]] = Field(
        default=None,
        description="Match exact sender email address.",
    )

    recipient_email: Optional[List[str]] = Field(
        default=None,
        description="Match exact recipient email address.",
    )

    cc_email: Optional[List[str]] = Field(
        default=None,
        description="Match exact CC recipient email address.",
    )

    project: Optional[List[str]] = Field(
        default=None,
        description="Match project identifiers.",
    )

    vendor: Optional[List[VendorType]] = Field(
        default=None,
        description="Match enterprise vendors.",
    )

    intent: Optional[List[str]] = Field(
        default=None,
        description="Match classified intent labels.",
    )

    only_cc: Optional[bool] = Field(
        default=None,
        description="Match emails where the recipient is CC only.",
    )

    has_attachment: Optional[bool] = Field(
        default=None,
        description="Match emails containing one or more attachments.",
    )


class RuleAction(BaseModel):
    """
    Deterministic actions applied when a rule matches.

    Responsibility:
        Defines folder, category, priority, importance, and vendor decisions
        parsed from YAML policy rule actions.

    Inputs:
        folder, subfolder, categories, priority, importance, vendor, project,
        flag, is_override_allowed.

    Outputs:
        RuleAction schema object.

    Role within Architecture:
        Infrastructure schema model used by PolicyRule.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    folder: Optional[FolderType] = Field(
        default=None,
        description="Destination folder.",
    )

    subfolder: Optional[str] = Field(
        default=None,
        description="Destination subfolder.",
    )

    categories: List[CategoryType] = Field(
        default_factory=list,
        description="Business categories to assign.",
    )

    priority: Optional[PriorityLevel] = Field(
        default=None,
        description="Priority level.",
    )

    importance: Optional[ImportanceLevel] = Field(
        default=None,
        description="Importance level.",
    )

    vendor: Optional[VendorType] = Field(
        default=None,
        description="Vendor classification.",
    )

    project: Optional[str] = Field(
        default=None,
        description="Project identifier.",
    )

    flag: bool = Field(
        default=False,
        description="Whether the email should be flagged.",
    )

    is_override_allowed: bool = Field(
        default=True,
        description="Whether downstream AI may override this action.",
    )


class PolicyRule(BaseModel):
    """
    A single policy rule definition.

    Responsibility:
        Pairs a rule condition with rule action decisions.

    Inputs:
        rule_id, name, enabled, condition, action.

    Outputs:
        PolicyRule schema object.

    Role within Architecture:
        Rule model within PolicyConfig.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rule_id: str = Field(
        ...,
        description="Unique rule identifier.",
    )

    name: str = Field(
        ...,
        description="Human-readable rule name.",
    )

    enabled: bool = Field(
        default=True,
        description="Whether this rule is active.",
    )

    condition: RuleCondition = Field(
        ...,
        description="Conditions required for the rule to match.",
    )

    action: RuleAction = Field(
        ...,
        description="Actions applied when the rule matches.",
    )


class FolderDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    path: str


class TaxonomyEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    display_name: str


class LabelPrefixesDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    priority: str
    importance: str
    vendor: str
    project: str
    category: str


class TaxonomyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    folders: dict[str, FolderDefinition]
    projects: dict[str, TaxonomyEntity]
    vendors: dict[str, TaxonomyEntity]
    categories: dict[str, TaxonomyEntity]
    label_prefixes: LabelPrefixesDefinition
    priorities: list[str]
    importance: list[str]


class PolicyConfig(BaseModel):
    """
    Root policy configuration loaded from policy_rules.yaml.

    Responsibility:
        Encapsulates version, name, taxonomy and list of PolicyRule instances loaded from YAML.

    Inputs:
        version, name, taxonomy, rules.

    Outputs:
        PolicyConfig schema object.

    Role within Architecture:
        Root configuration schema loaded by PolicyLoader and consumed by PolicyEngine.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: str = Field(
        default="1.0.0",
        description="Policy version.",
    )

    name: str = Field(
        default="Enterprise Email Policy",
        description="Policy name.",
    )

    taxonomy: Optional[TaxonomyConfig] = Field(
        default=None,
        description="Enterprise taxonomy configuration.",
    )

    rules: List[PolicyRule] = Field(
        default_factory=list,
        description="Ordered list of policy rules.",
    )
