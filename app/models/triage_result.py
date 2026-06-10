"""
TriageResult Model

Stores AI-generated analysis results for an email.

Relationship:
EMAILS (1) ---- (1) TRIAGE_RESULTS

Each email receives one AI triage result containing:
- Category
- Priority
- Summary
- Routing Recommendation
- Confidence Score
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.base import ModelBase


class TriageResult(ModelBase):
    """
    Stores AI-generated triage information for an email.
    """

    __tablename__ = "triage_results"

    # ------------------------------------------------------------------
    # Primary Key
    # ------------------------------------------------------------------

    triage_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # ------------------------------------------------------------------
    # Foreign Key
    # References emails.email_id
    # ------------------------------------------------------------------

    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.email_id"),
        nullable=False
    )

    # ------------------------------------------------------------------
    # AI Classification Output
    # ------------------------------------------------------------------

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    # AI-generated summary of the email
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Suggested routing destination
    routing_team: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Confidence score produced by the AI model
    # Example:
    # 0.95 = 95% confidence
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # Model used for inference
    # Example:
    # gpt-5
    # gemini-2.5
    model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # ------------------------------------------------------------------
    # Audit Fields
    # ------------------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )