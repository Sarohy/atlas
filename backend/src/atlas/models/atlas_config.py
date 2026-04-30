"""SQLAlchemy ORM model for ATLAS runtime configuration key-value store."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base


class AtlasConfig(Base):
    """Key-value pairs for ATLAS runtime configuration.

    Spec constants that must NOT be hardcoded in application code are stored
    here so they can be updated without a code deploy.

    Seed values (inserted by migration):
      f12_catalyst_window_days         = "7"
      f12_exit_deferral_trading_days   = "10"
    """

    __tablename__ = "atlas_config"

    # Primary key is the config key string itself.
    key: Mapped[str] = mapped_column(String(100), primary_key=True)

    # String-encoded value — caller is responsible for type conversion.
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional human-readable description of what this key controls.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
