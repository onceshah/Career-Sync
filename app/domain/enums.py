"""
Canonical business enums for the Enterprise AI Email Triage System.

Layer: Domain Layer
Role: Defines strongly-typed string enums for business categories, folders,
      priorities, vendors, conditions, and actions.

Interacting Components:
    - app.domain.models (Used across StructuredEmail and PolicyDecision)
    - app.domain.policy_engine (Rule evaluation and policy decisions)
    - app.ai.models (Used across AIDecision and ActionRecommendation)
    - app.infrastructure.config.schema (YAML policy configuration)
"""

from enum import Enum


class PriorityLevel(str, Enum):
    """
    Priority assigned to an email.

    Responsibility:
        Defines processing priority levels.
    """
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ImportanceLevel(str, Enum):
    """
    Email importance level.

    Responsibility:
        Defines email urgency/importance classification.
    """
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class CategoryType(str, Enum):
    """
    Business classification categories for the Career Copilot system.

    Responsibility:
        Defines categorization tags applied to emails.
    """
    JOB_OPPORTUNITY = "JOB_OPPORTUNITY"
    ONLINE_ASSESSMENT = "ONLINE_ASSESSMENT"
    INTERVIEW_INVITE = "INTERVIEW_INVITE"
    JOB_OFFER = "JOB_OFFER"
    REJECTION = "REJECTION"


class FolderType(str, Enum):
    """
    Logical destination folders for the Career Copilot system.

    Responsibility:
        Defines destination folders recommended by policy or AI engines.
    """
    LEADS = "LEADS"
    APPLICATIONS = "APPLICATIONS"
    ASSESSMENTS = "ASSESSMENTS"
    INTERVIEWS = "INTERVIEWS"
    OFFERS = "OFFERS"
    REJECTIONS = "REJECTIONS"
    ARCHIVE = "ARCHIVE"


class VendorType(str, Enum):
    """
    Recognized career platforms (represented as VendorType in schema placeholders).

    Responsibility:
        Identifies recognized career platforms.
    """
    INDEED = "INDEED"
    UNSTOP = "UNSTOP"
    LINKEDIN = "LINKEDIN"
    GLASSDOOR = "GLASSDOOR"
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    """
    Operational actions recommended by policy/AI.

    Responsibility:
        Defines discrete action types executable downstream.
    """
    MOVE_TO_FOLDER = "MOVE_TO_FOLDER"
    ADD_CATEGORY = "ADD_CATEGORY"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    ESCALATE = "ESCALATE"
    ARCHIVE = "ARCHIVE"
    IGNORE = "IGNORE"


class ConditionType(str, Enum):
    """
    Supported rule condition field types.

    Responsibility:
        Defines field matching keys evaluated by ConditionMatcher.
    """
    SUBJECT_CONTAINS = "subject_contains"
    BODY_CONTAINS = "body_contains"
    SENDER_DOMAIN = "sender_domain"
    RECIPIENT_DOMAIN = "recipient_domain"
    SENDER_EMAIL = "sender_email"
    PROJECT = "project"
    VENDOR = "vendor"
    INTENT = "intent"
