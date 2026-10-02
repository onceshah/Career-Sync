"""
Domain models for the Enterprise AI Email Triage System.

Layer: Domain Layer
Role: Defines canonical entity models and value objects passed between
      Ingestion, Policy Engine, AI Pipeline, and Execution layers.

Interacting Components:
    - app.domain.enums (Enum types)
    - app.ingestion.parser (Produces StructuredEmail)
    - app.domain.policy_engine (Consumes StructuredEmail, produces PolicyDecision)
    - app.ai.pipeline (Consumes StructuredEmail and PolicyDecision, produces AIDecision)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

try:
    from pydantic import EmailStr
except ImportError:
    EmailStr = str

from app.domain.enums import (
    ActionType,
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
)


# =============================================================================
# Base Model
# =============================================================================

class DomainModel(BaseModel):
    """
    Base model inherited by all domain entity and value object models.

    Responsibility:
        Centralizes Pydantic configuration to enforce strict field validation
        and preserve strongly-typed Enum objects across the domain layer.

    Inputs:
        Keyword arguments matching model field definitions.

    Outputs:
        Validated DomainModel instance.

    Role within Architecture:
        Domain Layer base class ensuring uniform behavior without converting
        Enums to primitive strings.
    """

    model_config = ConfigDict(
        extra="forbid",              # Reject unexpected fields
        validate_assignment=True,    # Validate when attributes are modified
        populate_by_name=True,
        frozen=False
    )


# =============================================================================
# Email Input Models
# =============================================================================

class EmailAddress(DomainModel):
    """
    Represents an email participant (sender or recipient).

    Responsibility:
        Validates display name and email address pairs.

    Inputs:
        name (Optional[str]): Human-readable display name.
        email (EmailStr): Validated email address.

    Outputs:
        EmailAddress domain object.

    Role within Architecture:
        Domain value object used in StructuredEmail.
    """

    name: Optional[str] = Field(
        default=None,
        description="Display name of the participant."
    )

    email: EmailStr = Field(
        description="Validated email address."
    )


# =============================================================================

class AttachmentMetadata(DomainModel):
    """
    Metadata describing an email attachment.

    Responsibility:
        Stores lightweight metadata for policy decision making without storing full payloads.

    Inputs:
        filename (str): Name of the attachment file.
        content_type (Optional[str]): MIME type of the file.
        size_bytes (int): File size in bytes.

    Outputs:
        AttachmentMetadata domain object.

    Role within Architecture:
        Domain value object attached to StructuredEmail.
    """

    filename: str = Field(
        min_length=1,
        description="Attachment filename."
    )

    content_type: Optional[str] = Field(
        default=None,
        description="MIME type."
    )

    size_bytes: int = Field(
        ge=0,
        description="Attachment size in bytes."
    )


# =============================================================================

class EmailHeaders(DomainModel):
    """
    Standard MIME and transport headers.

    Responsibility:
        Contains email message identification and threading headers.

    Inputs:
        message_id (Optional[str]): Unique message identifier.
        in_reply_to (Optional[str]): Parent message identifier.
        references (List[str]): Thread references list.

    Outputs:
        EmailHeaders domain object.

    Role within Architecture:
        Domain value object for message identification.
    """

    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: List[str] = Field(default_factory=list)


# =============================================================================

class StructuredEmail(DomainModel):
    """
    Canonical representation of an ingested and parsed email.

    Responsibility:
        Serves as the unified input domain contract across the policy and AI engines.

    Inputs:
        subject, body, sender, to, cc, bcc, headers, attachments, received_at,
        intent, project, vendor, keywords, entities, confidence, convenience flags.

    Outputs:
        StructuredEmail domain entity.

    Role within Architecture:
        Core Domain entity produced by ingestion and consumed by Rule/Policy & AI engines.
    """

    # -------------------------------------------------------------------------
    # Basic Email Information
    # -------------------------------------------------------------------------

    subject: str = Field(
        default="",
        description="Email subject line."
    )

    body: str = Field(
        default="",
        description="Plain text email body content."
    )

    sender: EmailAddress

    to: List[EmailAddress] = Field(
        default_factory=list
    )

    cc: List[EmailAddress] = Field(
        default_factory=list
    )

    bcc: List[EmailAddress] = Field(
        default_factory=list
    )

    headers: Optional[EmailHeaders] = None

    attachments: List[AttachmentMetadata] = Field(
        default_factory=list
    )

    received_at: Optional[datetime] = None

    # -------------------------------------------------------------------------
    # AI Extracted Information
    # -------------------------------------------------------------------------

    intent: Optional[str] = Field(
        default=None,
        description="Predicted email intent."
    )

    project: Optional[str] = Field(
        default=None,
        description="Detected project identifier."
    )

    vendor: VendorType = VendorType.UNKNOWN

    keywords: List[str] = Field(
        default_factory=list
    )

    entities: Dict[str, str] = Field(
        default_factory=dict
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score."
    )

    # -------------------------------------------------------------------------
    # Convenience Flags
    # -------------------------------------------------------------------------

    has_attachments: bool = False

    is_reply: bool = False

    is_forwarded: bool = False

    is_cc_only: bool = False

    # -------------------------------------------------------------------------
    # PII Privacy Boundary Metadata
    # -------------------------------------------------------------------------

    redacted: bool = Field(
        default=False,
        description="Whether mandatory Presidio PII redaction was applied at ingestion."
    )

    redaction_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-PII audit metadata from the Presidio redaction process."
    )



# =============================================================================
# Policy Engine Output Models
# =============================================================================


class ActionDecision(DomainModel):
    """
    Represents a single operational action recommended by the Policy Engine.

    Responsibility:
        Encapsulates action type enum and string parameters for execution layer processing.

    Inputs:
        action (ActionType): Action enum.
        parameters (Dict[str, str]): Action parameters dictionary.

    Outputs:
        ActionDecision domain object.

    Role within Architecture:
        Domain model representing executable or recommended operational actions.
    """

    action: ActionType = Field(
        description="Action recommended by the policy engine."
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters dictionary."
    )


# =============================================================================


class AuditInformation(DomainModel):
    """
    Captures policy evaluation audit trail and reasoning.

    Responsibility:
        Provides explainability and compliance tracing for policy decisions.

    Inputs:
        matched_rules (List[str]): Identifiers of matched rules.
        reasoning (List[str]): Explanation statements.
        policy_version (str): Configuration version string.
        evaluation_time_ms (float): Evaluation duration in milliseconds.

    Outputs:
        AuditInformation domain object.

    Role within Architecture:
        Domain audit record embedded within PolicyDecision.
    """

    matched_rules: List[str] = Field(
        default_factory=list,
        description="Identifiers of all matched business rules."
    )

    reasoning: List[str] = Field(
        default_factory=list,
        description="Human-readable explanation of the decision."
    )

    policy_version: str = Field(
        default="1.0.0",
        description="Policy configuration version."
    )

    evaluation_time_ms: float = Field(
        default=0.0,
        ge=0,
        description="Execution time of the policy evaluation."
    )


# =============================================================================


class ProcessingMetadata(DomainModel):
    """
    Metadata describing the policy evaluation execution environment.

    Responsibility:
        Stores processing timestamp and engine identification.

    Inputs:
        confidence (float): Processing confidence score.
        processed_at (datetime): UTC execution timestamp.
        processing_engine (str): Identifier of executing engine.

    Outputs:
        ProcessingMetadata domain object.

    Role within Architecture:
        Execution metadata container for PolicyDecision.
    """

    confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Confidence score inherited from processing."
    )

    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    processing_engine: str = Field(
        default="RulePolicyEngine"
    )


# =============================================================================


class PolicyDecision(DomainModel):
    """
    Canonical output of the Rule & Policy Engine.

    Responsibility:
        Contains strongly-typed enum decisions for destination folder, categories,
        vendor, priority, importance, recommended actions, and audit data.

    Inputs:
        folder (FolderType), subfolder, categories (List[CategoryType]),
        vendor (VendorType), priority (PriorityLevel), importance (ImportanceLevel),
        flag, actions, is_override_allowed, audit, metadata.

    Outputs:
        PolicyDecision domain model instance.

    Role within Architecture:
        Core Domain output object returned by PolicyEngine and consumed by AI Decision Pipeline.
    """

    # ---------------------------------------------------------------------
    # Folder Decision
    # ---------------------------------------------------------------------

    folder: FolderType = Field(
        description="Recommended logical folder."
    )

    subfolder: Optional[str] = Field(
        default=None,
        description="Optional subfolder path."
    )

    # ---------------------------------------------------------------------
    # Category Decision
    # ---------------------------------------------------------------------

    categories: List[CategoryType] = Field(
        default_factory=list,
        description="Recommended categories."
    )

    # ---------------------------------------------------------------------
    # Vendor Decision
    # ---------------------------------------------------------------------

    vendor: VendorType = Field(
        default=VendorType.UNKNOWN,
        description="Detected vendor."
    )

    # ---------------------------------------------------------------------
    # Priority
    # ---------------------------------------------------------------------

    priority: PriorityLevel = Field(
        default=PriorityLevel.NORMAL
    )

    importance: ImportanceLevel = Field(
        default=ImportanceLevel.NORMAL
    )

    flag: bool = Field(
        default=False,
        description="Whether the email should be flagged."
    )

    # ---------------------------------------------------------------------
    # Recommended Actions
    # ---------------------------------------------------------------------

    actions: List[ActionDecision] = Field(
        default_factory=list
    )

    is_override_allowed: bool = Field(
        default=True,
        description="Whether AI pipeline is permitted to override these decisions."
    )

    # ---------------------------------------------------------------------
    # Audit & Metadata
    # ---------------------------------------------------------------------

    audit: AuditInformation = Field(
        default_factory=AuditInformation
    )

    metadata: ProcessingMetadata = Field(
        default_factory=ProcessingMetadata
    )


# Re-exports for AI Pipeline decision models
from app.ai.models import AIDecision, ActionRecommendation

