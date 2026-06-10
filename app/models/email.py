from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.base import ModelBase


class Email(ModelBase):
    __tablename__ = "emails"

    email_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )