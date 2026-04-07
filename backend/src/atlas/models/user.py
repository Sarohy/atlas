"""User ORM model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base

EMAIL_LENGTH = 255
PASSWORD_HASH_LENGTH = 255
UUID_LENGTH = 36


class User(Base):
    """Application user used for sign-in."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(PASSWORD_HASH_LENGTH))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
