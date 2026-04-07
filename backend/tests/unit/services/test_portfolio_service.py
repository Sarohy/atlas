"""Unit tests for compute_portfolio_summary (pure function, no I/O)."""

from decimal import Decimal

import pytest

from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.services.portfolio_service import compute_portfolio_summary


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_config(
    cash: str = "0",
    floor_pct: str = "0.10",
) -> PortfolioConfig:
    return PortfolioConfig(
        id=PORTFOLIO_CONFIG_ROW_ID,
        cash_balance=Decimal(cash),
        cash_floor_pct=Decimal(floor_pct),
    )


def _make_ticker(
    symbol: str = "AAPL",
    shares: str = "100",
    position_value: str | None = None,
    beta: str | None = None,
    day_change: str | None = None,
) -> Ticker:
    return Ticker(
        ticker=symbol,
        company_name=f"{symbol} Inc.",
        shares=Decimal(shares),
        position_value=Decimal(position_value) if position_value else None,
        beta=Decimal(beta) if beta else None,
        day_change=Decimal(day_change) if day_change else None,
    )


# ── tests ─────────────────────────────────────────────────────────────────────

class TestComputePortfolioSummary:
    def test_empty_portfolio_total_nav_equals_cash(self) -> None:
        cfg = _make_config(cash="1000000")
        result = compute_portfolio_summary([], cfg)
        assert result.total_nav == Decimal("1000000")
        assert result.invested_value == Decimal("0")
        assert result.cash_balance == Decimal("1000000")

    def test_invested_and_cash_sum_to_total_nav(self) -> None:
        cfg = _make_config(cash="3585000")
        tickers = [
            _make_ticker("AAPL", position_value="10000000"),
            _make_ticker("NVDA", position_value="10315000"),
        ]
        result = compute_portfolio_summary(tickers, cfg)
        assert result.total_nav == Decimal("23900000")
        assert result.invested_value == Decimal("20315000")

    def test_cash_floor_computed_from_total_nav(self) -> None:
        cfg = _make_config(cash="3585000", floor_pct="0.10")
        tickers = [_make_ticker("AAPL", position_value="20315000")]
        result = compute_portfolio_summary(tickers, cfg)
        # floor = 23_900_000 × 0.10 = 2_390_000
        assert result.cash_floor == Decimal("2390000.0000")

    def test_deployable_is_cash_minus_floor(self) -> None:
        cfg = _make_config(cash="3585000", floor_pct="0.10")
        tickers = [_make_ticker("AAPL", position_value="20315000")]
        result = compute_portfolio_summary(tickers, cfg)
        # deployable = 3_585_000 − 2_390_000 = 1_195_000
        assert result.deployable == Decimal("1195000.0000")

    def test_deployable_is_never_negative(self) -> None:
        cfg = _make_config(cash="100", floor_pct="0.50")
        tickers = [_make_ticker("AAPL", position_value="100")]
        result = compute_portfolio_summary(tickers, cfg)
        # floor = 200 × 0.50 = 100; deployable = max(100 − 100, 0) = 0
        assert result.deployable == Decimal("0")

    def test_cash_floor_pct_in_response_is_percentage_not_fraction(self) -> None:
        cfg = _make_config(cash="0", floor_pct="0.10")
        result = compute_portfolio_summary([], cfg)
        # Response value should be 10.0, not 0.10
        assert result.cash_floor_pct == Decimal("10.0000")

    def test_beta_invested_weighted_by_position_value(self) -> None:
        cfg = _make_config(cash="0")
        tickers = [
            _make_ticker("AAPL", position_value="60", beta="1.0"),
            _make_ticker("NVDA", position_value="40", beta="2.0"),
        ]
        result = compute_portfolio_summary(tickers, cfg)
        # beta_invested = (1.0×60 + 2.0×40) / 100 = 140/100 = 1.40
        assert result.beta_invested is not None
        assert round(result.beta_invested, 4) == Decimal("1.4000")

    def test_beta_total_diluted_by_cash(self) -> None:
        cfg = _make_config(cash="50")
        tickers = [_make_ticker("AAPL", position_value="50", beta="2.0")]
        result = compute_portfolio_summary(tickers, cfg)
        # total_nav=100; beta_total = 2.0 × (50/100) = 1.0
        assert result.beta_total is not None
        assert round(result.beta_total, 4) == Decimal("1.0000")

    def test_beta_none_when_no_market_data(self) -> None:
        cfg = _make_config(cash="0")
        tickers = [_make_ticker("AAPL", position_value="1000", beta=None)]
        result = compute_portfolio_summary(tickers, cfg)
        assert result.beta_total is None
        assert result.beta_invested is None

    def test_day_change_aggregated_across_positions(self) -> None:
        cfg = _make_config(cash="0")
        tickers = [
            _make_ticker("AAPL", shares="100", day_change="1.50"),
            _make_ticker("NVDA", shares="50", day_change="-2.00"),
        ]
        result = compute_portfolio_summary(tickers, cfg)
        # 100×1.50 + 50×(−2.00) = 150 − 100 = 50
        assert result.day_change == Decimal("50")

    def test_day_change_none_when_no_sync_yet(self) -> None:
        cfg = _make_config(cash="0")
        tickers = [_make_ticker("AAPL", position_value="1000")]
        result = compute_portfolio_summary(tickers, cfg)
        assert result.day_change is None

    def test_pct_fields_sum_to_100_when_positive_nav(self) -> None:
        cfg = _make_config(cash="500")
        tickers = [_make_ticker("AAPL", position_value="500")]
        result = compute_portfolio_summary(tickers, cfg)
        assert round(result.invested_pct + result.cash_pct, 2) == Decimal("100.00")
