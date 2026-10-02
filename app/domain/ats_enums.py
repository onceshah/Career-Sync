"""
Canonical lifecycle state and review enums for CareerSync ATS State Engine (D5).
"""

from enum import Enum


class ApplicationLifecycleState(str, Enum):
    """
    Explicit CareerSync lifecycle taxonomy for job opportunities and applications.
    """
    DISCOVERED = "DISCOVERED"          # Job lead / campus drive identified
    INTERESTED = "INTERESTED"          # Saved by student for application
    APPLIED = "APPLIED"                # Application submitted & confirmed
    ASSESSMENT = "ASSESSMENT"          # Online test / coding challenge received/due
    INTERVIEW = "INTERVIEW"            # Technical / HR interview scheduled
    OFFER_SELECTED = "OFFER_SELECTED"  # Job offer extended or student selected
    REJECTED = "REJECTED"              # Application rejected
    WITHDRAWN = "WITHDRAWN"            # Application withdrawn by student
    EXPIRED = "EXPIRED"                # Opportunity / assessment deadline passed


class ReviewStatus(str, Enum):
    """
    Staging and audit review status flags for state transitions and entity resolution.
    """
    CONFIRMED = "CONFIRMED"            # Deterministically validated & committed
    NEEDS_REVIEW = "NEEDS_REVIEW"      # Low-confidence match or contradictory transition
    RESOLVED = "RESOLVED"              # Manually resolved by student
