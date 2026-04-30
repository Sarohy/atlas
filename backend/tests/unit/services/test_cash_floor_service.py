"""Unit tests for the Framework 5 Cash Floor service pure helpers and service class.

Tests cover:
  - _floor_params_from_rule  : regime → (condition, min_pct, max_pct, rationale)
  - _floor_usd_amounts        : position value × floor % → USD bounds
  - _get_floor_pct            : CLEAR transition logic (pure function)
  - _evaluate_floor_status    : cash vs floor → FloorStatus / warnings
  - CashFloorService.compute_cash_floor  : legacy ticker endpoint
  - CashFloorService.compute_portfolio_floor : new portfolio-level endpoint
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.models.portfolio_config import PortfolioConfig
from atlas.schemas.cash_floor import CashFloorResponse, FloorStatus, Framework5Response
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.cash_floor_service import (
    CashFloorService,
    _evaluate_floor_status,
    _floor_params_from_rule,
    _floor_usd_amounts,
    _get_floor_pct,
)


# ---------------------------------------------------------------------------
# _floor_params_from_rule — updated regime names and floor values
# ---------------------------------------------------------------------------


class TestFloorParamsFromRule:
    def test_crisis_halt_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CRISIS HALT")
        assert condition == "CRISIS HALT"

    def test_crisis_halt_floor_value(self) -> None:
        _, floor_min, floor_max, _ = _floor_params_from_rule("CRISIS HALT")
        assert floor_min == pytest.approx(0.30)
        assert floor_max == pytest.approx(0.30)

    def test_crisis_halt_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CRISIS HALT")
        assert "binary weekend risk" in rationale.lower() or "high beta" in rationale.lower()

    def test_caution_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CAUTION")
        assert condition == "CAUTION"

    def test_caution_floor_value(self) -> None:
        _, floor_min, floor_max, _ = _floor_params_from_rule("CAUTION")
        assert floor_min == pytest.approx(0.20)
        assert floor_max == pytest.approx(0.20)

    def test_caution_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CAUTION")
        assert "T1" in rationale

    def test_soft_caution_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("SOFT CAUTION")
        assert condition == "SOFT CAUTION"

    def test_soft_caution_floor_value(self) -> None:
        _, floor_min, floor_max, _ = _floor_params_from_rule("SOFT CAUTION")
        assert floor_min == pytest.approx(0.15)
        assert floor_max == pytest.approx(0.15)

    def test_soft_caution_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("SOFT CAUTION")
        assert rationale  # non-empty string

    def test_clear_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CLEAR")
        assert condition == "CLEAR"

    def test_clear_floor_conservative_default(self) -> None:
        # Legacy endpoint uses conservative 10% default for CLEAR
        _, floor_min, floor_max, _ = _floor_params_from_rule("CLEAR")
        assert floor_min == pytest.approx(0.10)
        assert floor_max == pytest.approx(0.10)

    def test_clear_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CLEAR")
        assert "macro buffer" in rationale.lower() or "8%" in rationale or "hedge" in rationale.lower()

    def test_normal_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("NORMAL")
        assert condition == "FULLY_DEPLOYED"

    def test_normal_floor_value(self) -> None:
        _, floor_min, floor_max, _ = _floor_params_from_rule("NORMAL")
        assert floor_min == pytest.approx(0.10)
        assert floor_max == pytest.approx(0.10)

    def test_normal_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("NORMAL")
        assert "never" in rationale.lower()

    def test_unknown_rule_falls_back_to_fully_deployed(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("UNKNOWN_REGIME")
        assert condition == "FULLY_DEPLOYED"


# ---------------------------------------------------------------------------
# _floor_usd_amounts — unchanged logic
# ---------------------------------------------------------------------------


class TestFloorUsdAmounts:
    def test_crisis_position_10000(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("10000.00"), 0.30, 0.30)
        assert min_usd == Decimal("3000.00")
        assert max_usd == Decimal("3000.00")

    def test_clear_position_50000(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("50000.00"), 0.08, 0.08)
        assert min_usd == Decimal("4000.00")
        assert max_usd == Decimal("4000.00")

    def test_floor_min_equals_max(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("20000.00"), 0.20, 0.20)
        assert min_usd == max_usd
        assert min_usd == Decimal("4000.00")

    def test_none_position_value_returns_none_bounds(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(None, 0.30, 0.30)
        assert min_usd is None
        assert max_usd is None

    def test_result_rounded_to_cents(self) -> None:
        # 333.33 * 0.20 = 66.666 → should round to 66.67
        min_usd, _ = _floor_usd_amounts(Decimal("333.33"), 0.20, 0.20)
        assert min_usd is not None
        assert min_usd == Decimal("66.67")

    def test_zero_position_value(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("0.00"), 0.30, 0.30)
        assert min_usd == Decimal("0.00")
        assert max_usd == Decimal("0.00")


# ---------------------------------------------------------------------------
# _get_floor_pct — CLEAR transition logic
# ---------------------------------------------------------------------------


class TestGetFloorPct:
    _TODAY = datetime.date(2026, 6, 1)

    def test_crisis_halt_returns_30_no_transition(self) -> None:
        floor_pct, transition_active, days = _get_floor_pct("CRISIS HALT", None, self._TODAY)
        assert floor_pct == pytest.approx(0.30)
        assert transition_active is False
        assert days is None

    def test_caution_returns_20_no_transition(self) -> None:
        floor_pct, transition_active, days = _get_floor_pct("CAUTION", None, self._TODAY)
        assert floor_pct == pytest.approx(0.20)
        assert transition_active is False
        assert days is None

    def test_soft_caution_returns_15_no_transition(self) -> None:
        floor_pct, transition_active, days = _get_floor_pct("SOFT CAUTION", None, self._TODAY)
        assert floor_pct == pytest.approx(0.15)
        assert transition_active is False
        assert days is None

    def test_clear_no_transition_date_returns_10_transition_14(self) -> None:
        floor_pct, transition_active, days = _get_floor_pct("CLEAR", None, self._TODAY)
        assert floor_pct == pytest.approx(0.10)
        assert transition_active is True
        assert days == 14

    def test_clear_transition_started_today_returns_10_days_14(self) -> None:
        floor_pct, transition_active, days = _get_floor_pct("CLEAR", self._TODAY, self._TODAY)
        assert floor_pct == pytest.approx(0.10)
        assert transition_active is True
        assert days == 14

    def test_clear_transition_7_days_ago_returns_10_days_7(self) -> None:
        transition_date = self._TODAY - datetime.timedelta(days=7)
        floor_pct, transition_active, days = _get_floor_pct("CLEAR", transition_date, self._TODAY)
        assert floor_pct == pytest.approx(0.10)
        assert transition_active is True
        assert days == 7

    def test_clear_transition_14_days_ago_returns_8_settled(self) -> None:
        transition_date = self._TODAY - datetime.timedelta(days=14)
        floor_pct, transition_active, days = _get_floor_pct("CLEAR", transition_date, self._TODAY)
        assert floor_pct == pytest.approx(0.08)
        assert transition_active is False
        assert days is None

    def test_clear_transition_20_days_ago_returns_8_settled(self) -> None:
        transition_date = self._TODAY - datetime.timedelta(days=20)
        floor_pct, transition_active, days = _get_floor_pct("CLEAR", transition_date, self._TODAY)
        assert floor_pct == pytest.approx(0.08)
        assert transition_active is False
        assert days is None


# ---------------------------------------------------------------------------
# _evaluate_floor_status
# ---------------------------------------------------------------------------


class TestEvaluateFloorStatus:
    """
    Signature: _evaluate_floor_status(total_cash, floor_amount, buffer_pct)
    Returns:   (FloorStatus, warning_level, warning_message, deployment_permitted)
    """

    def test_zero_cash_returns_critical_zero(self) -> None:
        status, warning_level, msg, deployment = _evaluate_floor_status(0.0, 1000.0, 0.0)
        assert status == FloorStatus.CRITICAL_ZERO
        assert warning_level == "CRITICAL"
        assert deployment is False

    def test_below_floor_returns_below_floor_status(self) -> None:
        # cash=500, floor=1000 — clearly below
        status, warning_level, msg, deployment = _evaluate_floor_status(500.0, 1000.0, 0.0)
        assert status == FloorStatus.BELOW_FLOOR
        assert warning_level == "CRITICAL"
        assert deployment is False

    def test_below_floor_message_mentions_shortfall(self) -> None:
        status, _, msg, _ = _evaluate_floor_status(500.0, 1000.0, 0.0)
        assert msg is not None
        assert "500" in msg or "floor" in msg.lower()

    def test_at_floor_returns_at_floor_status(self) -> None:
        # cash == floor exactly
        status, warning_level, _, deployment = _evaluate_floor_status(1000.0, 1000.0, 0.0)
        assert status == FloorStatus.AT_FLOOR
        assert warning_level == "AMBER"
        assert deployment is False

    def test_low_buffer_returns_low_buffer_status(self) -> None:
        # buffer_pct = 0.005 < 0.01 threshold → LOW_BUFFER
        status, warning_level, _, deployment = _evaluate_floor_status(1050.0, 1000.0, 0.005)
        assert status == FloorStatus.LOW_BUFFER
        assert warning_level == "AMBER"
        assert deployment is True

    def test_healthy_returns_healthy_status(self) -> None:
        # buffer_pct = 0.05 > 0.01 threshold → HEALTHY
        status, warning_level, msg, deployment = _evaluate_floor_status(1200.0, 1000.0, 0.05)
        assert status == FloorStatus.HEALTHY
        assert warning_level == "NONE"
        assert msg is None
        assert deployment is True


# ---------------------------------------------------------------------------
# Fixtures shared by TestComputeCashFloor and TestComputePortfolioFloor
# ---------------------------------------------------------------------------


def _make_regime_response(
    rule_int: int | None,
    rule_str: str,
    brent: float = 75.0,
    vix: float = 18.0,
) -> RegimeModifierResponse:
    """Construct a minimal RegimeModifierResponse for a given regime."""
    return RegimeModifierResponse(
        ticker="PORTFOLIO",
        geopolitical_state="NONE",
        brent_price=brent,
        vix_value=vix,
        brent_consecutive_below_95_count=0,
        base_score=60,
        adjusted_score=60,
        rule_triggered=rule_int,
        rule=rule_str,
        effective_regime=rule_str,
        modifier=0,
        min_cash_pct=0.10,
        max_cash_pct=0.20,
        min_cash_usd=None,
        max_cash_usd=None,
        output_text="",
        determination_text="",
    )


_CAUTION_REGIME = _make_regime_response(2, "CAUTION", brent=75.0, vix=28.0)
_CRISIS_HALT_REGIME = _make_regime_response(1, "CRISIS HALT", brent=115.0, vix=40.0)
_SOFT_CAUTION_REGIME = _make_regime_response(3, "SOFT CAUTION", brent=92.0, vix=18.0)
_CLEAR_REGIME = _make_regime_response(4, "CLEAR", brent=88.0, vix=16.0)


def _make_service(session: AsyncMock) -> CashFloorService:
    """Construct a CashFloorService with dummy API keys and a mock session."""
    return CashFloorService(
        polygon_api_key="test",
        alphavantage_api_key="test",
        transcript_api_key="test",
        benzinga_api_key="test",
        unusual_whales_api_key="test",
        sec_api_key="test",
        session=session,
    )


def _mock_session_scalar(cash_balance: Decimal) -> AsyncMock:
    """Return an async session mock that yields `cash_balance` from execute()."""
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = cash_balance
    session = AsyncMock()
    session.execute = AsyncMock(return_value=scalar_result)
    return session


def _mock_session_with_config(
    cash_balance: Decimal,
    clear_transition_date: datetime.date | None = None,
) -> tuple[AsyncMock, MagicMock]:
    """Return (session, config_mock) for compute_portfolio_floor tests."""
    config = MagicMock(spec=PortfolioConfig)
    config.cash_balance = cash_balance
    config.clear_transition_date = clear_transition_date

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = config

    session = AsyncMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()
    return session, config


def _make_ticker(position_value: Decimal) -> MagicMock:
    t = MagicMock()
    t.position_value = position_value
    return t


# ---------------------------------------------------------------------------
# CashFloorService.compute_cash_floor — legacy ticker endpoint
# ---------------------------------------------------------------------------


class TestComputeCashFloor:
    """Tests for CashFloorService.compute_cash_floor using mocked dependencies."""

    @pytest.mark.asyncio
    async def test_uses_total_nav_caution_20pct(self) -> None:
        """CAUTION floor is 20% of total NAV (not 25%)."""
        session = _mock_session_scalar(Decimal("500000.00"))  # cash balance
        service = _make_service(session)

        ticker_a = _make_ticker(Decimal("1000000.00"))
        ticker_b = _make_ticker(Decimal("500000.00"))
        # total_nav = 1_000_000 + 500_000 + 500_000 = 2_000_000
        # CAUTION floor = 20% → 400_000

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[ticker_a, ticker_b]),
            ),
        ):
            result: CashFloorResponse = await service.compute_cash_floor("MU")

        assert result.position_value_usd == pytest.approx(2_000_000.0)
        assert result.floor_usd_min == pytest.approx(400_000.0)

    @pytest.mark.asyncio
    async def test_cash_balance_included_in_response(self) -> None:
        """cash_balance field must be populated from the portfolio config row."""
        session = _mock_session_scalar(Decimal("250000.00"))
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("750000.00"))]),
            ),
        ):
            result = await service.compute_cash_floor("MU")

        assert result.cash_balance == pytest.approx(250_000.0)

    @pytest.mark.asyncio
    async def test_zero_total_nav_yields_none_floor_amounts(self) -> None:
        """When total NAV is 0 (no positions, no cash), USD floor amounts must be None."""
        session = _mock_session_scalar(Decimal("0.00"))
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await service.compute_cash_floor("MU")

        assert result.position_value_usd is None
        assert result.floor_usd_min is None
        assert result.floor_usd_max is None

    @pytest.mark.asyncio
    async def test_regime_fallback_on_unexpected_error(self) -> None:
        """A non-RegimeModifierResponse return must fall back to FULLY_DEPLOYED."""
        session = _mock_session_scalar(Decimal("1000.00"))
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value="unexpected"),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await service.compute_cash_floor("MU")

        assert result.condition == "FULLY_DEPLOYED"
        assert result.brent_price is None
        assert result.vix_value is None


# ---------------------------------------------------------------------------
# CashFloorService.compute_portfolio_floor — new portfolio-level endpoint
# ---------------------------------------------------------------------------

# Minimal PortfolioBetaResult stand-in for the calculate_portfolio_beta mock.
_BETA_RESULT_NORMAL = MagicMock()
_BETA_RESULT_NORMAL.effective_beta = 1.50
_BETA_RESULT_NORMAL.target_beta = 1.75
_BETA_RESULT_NORMAL.beta_status = "NORMAL"


class TestComputePortfolioFloor:
    """Tests for CashFloorService.compute_portfolio_floor."""

    @pytest.mark.asyncio
    async def test_caution_regime_sets_20pct_floor(self) -> None:
        """CAUTION regime → floor_pct = 0.20, floor_amount = 20% of total_nav."""
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
            clear_transition_date=None,
        )
        service = _make_service(session)
        # total_nav = 1_500_000 + 500_000 = 2_000_000
        # floor = 20% → 400_000

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("1500000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result: Framework5Response = await service.compute_portfolio_floor()

        assert result.regime == "CAUTION"
        assert result.floor_pct == pytest.approx(0.20)
        assert result.floor_amount == pytest.approx(400_000.0)
        assert result.total_nav == pytest.approx(2_000_000.0)

    @pytest.mark.asyncio
    async def test_crisis_halt_regime_sets_30pct_floor(self) -> None:
        """CRISIS HALT regime → floor_pct = 0.30."""
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("1000000.00"),
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CRISIS_HALT_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("4000000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.regime == "CRISIS HALT"
        assert result.floor_pct == pytest.approx(0.30)

    @pytest.mark.asyncio
    async def test_soft_caution_regime_sets_15pct_floor(self) -> None:
        """SOFT CAUTION regime → floor_pct = 0.15."""
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_SOFT_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("2000000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.regime == "SOFT CAUTION"
        assert result.floor_pct == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_clear_no_transition_date_sets_10pct_transition(self) -> None:
        """CLEAR + no stored transition date → 10% floor, transition_active=True."""
        session, config = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
            clear_transition_date=None,
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CLEAR_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("2000000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.floor_pct == pytest.approx(0.10)
        assert result.transition_active is True

    @pytest.mark.asyncio
    async def test_clear_old_transition_date_sets_8pct_settled(self) -> None:
        """CLEAR + transition date > 14 days ago → 8% floor, transition_active=False."""
        old_date = datetime.date.today() - datetime.timedelta(days=20)
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
            clear_transition_date=old_date,
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CLEAR_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("2000000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.floor_pct == pytest.approx(0.08)
        assert result.transition_active is False

    @pytest.mark.asyncio
    async def test_below_floor_sets_is_below_floor_and_blocks_deployment(self) -> None:
        """When cash < floor, is_below_floor=True and deployment_permitted=False."""
        # CAUTION 20% floor → 2_000_000 * 0.20 = 400_000 floor
        # cash = 100_000 < 400_000 → BELOW FLOOR
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("100000.00"),
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("1900000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.is_below_floor is True
        assert result.deployment_permitted is False
        assert result.floor_status == FloorStatus.BELOW_FLOOR

    @pytest.mark.asyncio
    async def test_healthy_cash_permits_deployment(self) -> None:
        """When cash well above floor, deployment_permitted=True, HEALTHY status."""
        # CAUTION 20% floor → 2_000_000 * 0.20 = 400_000 floor
        # cash = 800_000 (40%) → buffer = 400_000 → HEALTHY
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("800000.00"),
        )
        service = _make_service(session)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("1200000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.is_below_floor is False
        assert result.deployment_permitted is True
        assert result.floor_status == FloorStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_effective_beta_passed_through(self) -> None:
        """effective_beta in response must match the portfolio beta result."""
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
        )
        service = _make_service(session)

        beta_result = MagicMock()
        beta_result.effective_beta = 1.82
        beta_result.target_beta = 1.75
        beta_result.beta_status = "ELEVATED"

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=_CAUTION_REGIME),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("1500000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=beta_result),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.effective_beta == pytest.approx(1.82)
        assert result.beta_status == "ELEVATED"

    @pytest.mark.asyncio
    async def test_brent_and_vix_included_in_response(self) -> None:
        """Brent and VIX from Framework 2 response must appear in Framework5Response."""
        session, _ = _mock_session_with_config(
            cash_balance=Decimal("500000.00"),
        )
        service = _make_service(session)
        regime = _make_regime_response(2, "CAUTION", brent=102.50, vix=27.80)

        with (
            patch.object(
                service._regime_service,
                "compute_regime_modifier",
                new=AsyncMock(return_value=regime),
            ),
            patch.object(
                service._ticker_service,
                "list_tickers",
                new=AsyncMock(return_value=[_make_ticker(Decimal("1500000.00"))]),
            ),
            patch(
                "atlas.services.cash_floor_service.calculate_portfolio_beta",
                new=AsyncMock(return_value=_BETA_RESULT_NORMAL),
            ),
        ):
            result = await service.compute_portfolio_floor()

        assert result.brent_price == pytest.approx(102.50)
        assert result.vix_value == pytest.approx(27.80)

