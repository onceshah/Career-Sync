"""
AuditLog Model

Stores change history for emails and triage actions.

Purpose:
- Track modifications
- Support auditing
- Support troubleshooting
- Maintain change history
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


class AuditLog(ModelBase):
    """
    Stores audit events related to an email.
    """

    __tablename__ = "audit_logs"

    # --------------------------------------------------
    # Primary Key
    # --------------------------------------------------

    audit_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # --------------------------------------------------
    # Foreign Key
    # --------------------------------------------------

    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.email_id"),
        nullable=False
    )

    # --------------------------------------------------
    # Audit Event
    # --------------------------------------------------

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Previous value before change
    old_value: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # Updated value after change
    new_value: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # --------------------------------------------------
    # Audit Timestamp
    # --------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )