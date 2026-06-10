"""
Feedback Model

Stores human review and corrections of AI-generated triage results.

Purpose:
- Measure AI classification accuracy
- Measure routing accuracy
- Track human overrides
- Generate future training data
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.base import ModelBase


class Feedback(ModelBase):
    """
    Stores reviewer feedback for a processed email.
    """

    __tablename__ = "feedback"

    # --------------------------------------------------
    # Primary Key
    # --------------------------------------------------

    feedback_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # --------------------------------------------------
    # Foreign Key
    # References emails.email_id
    # --------------------------------------------------

    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.email_id"),
        nullable=False
    )

    # --------------------------------------------------
    # AI Prediction
    # --------------------------------------------------

    original_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    original_routing: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # --------------------------------------------------
    # Human Correction
    # --------------------------------------------------

    corrected_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    corrected_routing: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # --------------------------------------------------
    # Reviewer Notes
    # --------------------------------------------------

    review_notes: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # --------------------------------------------------
    # Audit Timestamp
    # --------------------------------------------------

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )