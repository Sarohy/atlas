"""Business logic for portfolio summary and cash management."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.portfolio import CashUpdateRequest, PortfolioSummaryResponse


def compute_portfolio_summary(
    tickers: list[Ticker],
    config: PortfolioConfig,
) -> PortfolioSummaryResponse:
    """Compute the full portfolio summary from positions and cash config.

    Pure function — no I/O, no side effects, fully unit-testable.
    """
    invested_value: Decimal = sum(
        (t.position_value or Decimal("0")) for t in tickers
    ) or Decimal("0")
    cash_balance = config.cash_balance
    total_nav = invested_value + cash_balance

    if total_nav > 0:
        invested_pct = (invested_value / total_nav * 100).quantize(Decimal("0.0001"))
        cash_pct = (cash_balance / total_nav * 100).quantize(Decimal("0.0001"))
    else:
        invested_pct = Decimal("0")
        cash_pct = Decimal("0")

    cash_floor = (total_nav * config.cash_floor_pct).quantize(Decimal("0.0001"))
    # cash_floor_pct in the response is % (0–100), not fraction (0–1).
    cash_floor_pct_display = (config.cash_floor_pct * 100).quantize(Decimal("0.0001"))
    deployable = max(cash_balance - cash_floor, Decimal("0")).quantize(Decimal("0.0001"))

    # Day-change: sum of per-share dollar change × number of shares held.
    positions_with_change = [t for t in tickers if t.day_change is not None]
    day_change: Decimal | None = (
        sum(
            t.day_change * t.shares  # type: ignore[operator]
            for t in positions_with_change
        )
        if positions_with_change
        else None
    )

    # Weighted-average beta (weight = position_value / invested_value).
    valued_tickers = [
        t
        for t in tickers
        if t.beta is not None
        and t.position_value is not None
        and t.position_value > 0
    ]
    beta_invested: Decimal | None = None
    beta_total: Decimal | None = None
    if valued_tickers and invested_value > 0:
        beta_invested = sum(
            t.beta * t.position_value / invested_value  # type: ignore[operator]
            for t in valued_tickers
        ).quantize(Decimal("0.0001"))
        if total_nav > 0:
            beta_total = (beta_invested * invested_value / total_nav).quantize(
                Decimal("0.0001")
            )

    return PortfolioSummaryResponse(
        total_nav=total_nav,
        invested_value=invested_value,
        invested_pct=invested_pct,
        cash_balance=cash_balance,
        cash_pct=cash_pct,
        cash_floor=cash_floor,
        cash_floor_pct=cash_floor_pct_display,
        deployable=deployable,
        day_change=day_change,
        beta_total=beta_total,
        beta_invested=beta_invested,
    )


class PortfolioService:
    """Database interactions for portfolio configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_config(self) -> PortfolioConfig:
        """Return the singleton PortfolioConfig row, creating it if absent."""
        config = await self._session.get(PortfolioConfig, PORTFOLIO_CONFIG_ROW_ID)
        if config is None:
            config = PortfolioConfig(
                id=PORTFOLIO_CONFIG_ROW_ID,
                cash_balance=Decimal("0.00"),
                cash_floor_pct=PortfolioConfig.CASH_FLOOR_PCT_DEFAULT,
            )
            self._session.add(config)
            await self._session.flush()
            await self._session.refresh(config)
        return config

    async def update_cash(self, data: CashUpdateRequest) -> PortfolioConfig:
        """Persist updated cash settings and return the refreshed config."""
        config = await self.get_or_create_config()
        config.cash_balance = data.cash_balance
        config.cash_floor_pct = data.cash_floor_pct
        await self._session.flush()
        await self._session.refresh(config)
        return config
