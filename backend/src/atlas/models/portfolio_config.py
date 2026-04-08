"""SQLAlchemy ORM model for portfolio-wide configuration (singleton row)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db.base import Base

# The single row's primary key — there must only ever be one row.
PORTFOLIO_CONFIG_ROW_ID: int = 1


class PortfolioConfig(Base):
    """Singleton table storing portfolio-level cash settings.

    Only one row (id=PORTFOLIO_CONFIG_ROW_ID) should ever exist.
    Use ``PortfolioService.get_or_create_config()`` to fetch it safely.
    """

    __tablename__ = "portfolio_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=PORTFOLIO_CONFIG_ROW_ID)

    # Total cash held outside positions, stored in USD with 2 decimal places.
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Fraction of total NAV to keep as the hard cash floor (0.10 = 10 %).
    # Stored as a fraction so arithmetic stays clean; multiply by 100 for display.
    CASH_FLOOR_PCT_DEFAULT: Decimal = Decimal("0.10")
    cash_floor_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4),
        nullable=False,
        default=CASH_FLOOR_PCT_DEFAULT,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioConfig cash={self.cash_balance} floor_pct={self.cash_floor_pct}>"
        )
