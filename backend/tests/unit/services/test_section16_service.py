"""Tests for Section 16 Exit Rules service.

TDD: these tests are written FIRST and should FAIL until section16_service.py exists.

Test plan (18 cases):
  TestGetLastFridayDate         (3) — date logic, pure
  TestRule161ScoreBased         (5) — two-cycle, reconciliation pause, F12 deferral
  TestRule162GapDown            (3) — threshold, hold window, status
  TestRule163AppreciationTrim   (3) — below/soft/hard cap, NAV data missing
  TestRule164PutProtection      (4) — all-4-conditions, partial, none
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TestGetLastFridayDate
# ---------------------------------------------------------------------------


class TestGetLastFridayDate:
    """get_last_friday_date() must return the most recent completed Friday in ET."""

    def test_when_today_is_saturday_returns_yesterday(self) -> None:
        """Saturday → previous day (Friday)."""
        from atlas.services.section16_service import get_last_friday_date

        # 2026-04-18 is a Saturday
        fixed_today = date(2026, 4, 18)
        result = get_last_friday_date(today=fixed_today)
        assert result == date(2026, 4, 17)

    def test_when_today_is_friday_after_close_returns_today(self) -> None:
        """Friday after 16:00 ET → today (rescore is complete)."""
        from atlas.services.section16_service import get_last_friday_date

        # 2026-04-17 is a Friday; caller passes after_close=True
        fixed_today = date(2026, 4, 17)
        result = get_last_friday_date(today=fixed_today, after_close=True)
        assert result == date(2026, 4, 17)

    def test_when_today_is_friday_before_close_returns_previous_friday(self) -> None:
        """Friday before 16:00 ET → previous Friday (rescore not yet complete)."""
        from atlas.services.section16_service import get_last_friday_date

        fixed_today = date(2026, 4, 17)
        result = get_last_friday_date(today=fixed_today, after_close=False)
        assert result == date(2026, 4, 10)

    def test_when_today_is_monday_returns_previous_friday(self) -> None:
        """Monday → three days prior (Friday)."""
        from atlas.services.section16_service import get_last_friday_date

        # 2026-04-20 is a Monday
        fixed_today = date(2026, 4, 20)
        result = get_last_friday_date(today=fixed_today)
        assert result == date(2026, 4, 17)

    def test_when_today_is_wednesday_returns_previous_friday(self) -> None:
        """Wednesday → five days prior (Friday)."""
        from atlas.services.section16_service import get_last_friday_date

        # 2026-04-22 is a Wednesday
        fixed_today = date(2026, 4, 22)
        result = get_last_friday_date(today=fixed_today)
        assert result == date(2026, 4, 17)


# ---------------------------------------------------------------------------
# TestRule161ScoreBased
# ---------------------------------------------------------------------------


def _make_session_with_config(**config_overrides: str) -> AsyncMock:
    """Return a mock AsyncSession whose .get() returns AtlasConfig rows."""
    from atlas.models.atlas_config import AtlasConfig

    defaults: dict[str, str] = {
        "s16_score_below_55_threshold": "55",
        "s16_score_below_45_threshold": "45",
        "s16_trim_pct_cycle_two": "50",
        "s16_trim_window_trading_days": "5",
        "s16_full_exit_trading_days": "3",
        "s16_gap_down_threshold_pct": "20",
        "s16_gap_down_hold_hours": "48",
        "s16_gap_down_rescore_hours": "72",
        "s16_appreciation_soft_cap_pct": "8",
        "s16_appreciation_hard_cap_pct": "10",
        "s16_appreciation_trim_size_pct": "20",
        "s16_put_flow_threshold_usd": "500000",
        "s16_put_earnings_days": "20",
        "s16_reconciliation_gap_threshold": "8",
        "s16_catalyst_deferral_days": "10",
    }
    defaults.update(config_overrides)

    session = AsyncMock()

    def _get_side_effect(model: type, key: str) -> Any:
        if model is AtlasConfig and key in defaults:
            row = MagicMock(spec=AtlasConfig)
            row.value = defaults[key]
            return row
        return None

    session.get = AsyncMock(side_effect=_get_side_effect)
    return session


class TestRule161ScoreBased:
    """Rule 16.1: score-based two-cycle exit logic."""

    @pytest.fixture()
    def mock_session(self) -> AsyncMock:
        return _make_session_with_config()

    @pytest.mark.asyncio
    async def test_score_above_55_cycle_cleared(self, mock_session: AsyncMock) -> None:
        """Score ≥ 55 at Friday rescore — no cycle, status CLEAR."""
        from atlas.services.section16_service import evaluate_rule_161

        result = await evaluate_rule_161(
            ticker="NVDA",
            current_friday_score=68.0,
            cycle_record=None,
            f12_no_fly_active=False,
            reconciliation_pending=False,
            session=mock_session,
        )

        assert result["status"] == "CLEAR"
        assert result["cycle_count"] == 0
        assert result["trim_triggered"] is False
        assert result["full_exit_triggered"] is False

    @pytest.mark.asyncio
    async def test_first_cycle_below_55_returns_watch(
        self, mock_session: AsyncMock
    ) -> None:
        """Score < 55 with no prior cycle → CYCLE_ONE (WATCH)."""
        from atlas.services.section16_service import evaluate_rule_161

        result = await evaluate_rule_161(
            ticker="NBIS",
            current_friday_score=51.5,
            cycle_record=None,
            f12_no_fly_active=False,
            reconciliation_pending=False,
            session=mock_session,
        )

        assert result["status"] == "CYCLE_ONE"
        assert result["cycle_count"] == 1
        assert result["trim_triggered"] is False
        assert result["full_exit_triggered"] is False

    @pytest.mark.asyncio
    async def test_second_cycle_below_55_triggers_trim(
        self, mock_session: AsyncMock
    ) -> None:
        """Score < 55 with existing CYCLE_ONE record → trim 50% triggered."""
        from atlas.services.section16_service import evaluate_rule_161

        cycle_record = {
            "cycle_status": "CYCLE_ONE",
            "cycle_one_date": date(2026, 4, 17),
            "cycle_one_score": 51.5,
            "reconciliation_pause": False,
            "deferred_until": None,
        }

        result = await evaluate_rule_161(
            ticker="NBIS",
            current_friday_score=52.0,
            cycle_record=cycle_record,
            f12_no_fly_active=False,
            reconciliation_pending=False,
            session=mock_session,
        )

        assert result["status"] == "CYCLE_TWO"
        assert result["cycle_count"] == 2
        assert result["trim_triggered"] is True
        assert result["full_exit_triggered"] is False

    @pytest.mark.asyncio
    async def test_score_below_45_triggers_full_exit(
        self, mock_session: AsyncMock
    ) -> None:
        """Score < 45 regardless of cycle count → FULL_EXIT within 3 trading days."""
        from atlas.services.section16_service import evaluate_rule_161

        result = await evaluate_rule_161(
            ticker="NBIS",
            current_friday_score=42.0,
            cycle_record=None,
            f12_no_fly_active=False,
            reconciliation_pending=False,
            session=mock_session,
        )

        assert result["full_exit_triggered"] is True
        assert result["exit_window_trading_days"] == 3

    @pytest.mark.asyncio
    async def test_reconciliation_pause_prevents_cycle_accrual(
        self, mock_session: AsyncMock
    ) -> None:
        """When reconciliation_pending=True, cycle_count does NOT advance."""
        from atlas.services.section16_service import evaluate_rule_161

        cycle_record = {
            "cycle_status": "CYCLE_ONE",
            "cycle_one_date": date(2026, 4, 17),
            "cycle_one_score": 51.5,
            "reconciliation_pause": True,
            "deferred_until": None,
        }

        result = await evaluate_rule_161(
            ticker="NBIS",
            current_friday_score=50.0,
            cycle_record=cycle_record,
            f12_no_fly_active=False,
            reconciliation_pending=True,
            session=mock_session,
        )

        assert result["status"] == "CYCLE_ONE_PAUSED"
        assert result["cycle_count"] == 1
        assert result["trim_triggered"] is False

    @pytest.mark.asyncio
    async def test_f12_deferral_defers_trim_window(
        self, mock_session: AsyncMock
    ) -> None:
        """When f12_no_fly_active=True and score triggers trim, status is DEFERRED not TRIM."""
        from atlas.services.section16_service import evaluate_rule_161

        cycle_record = {
            "cycle_status": "CYCLE_ONE",
            "cycle_one_date": date(2026, 4, 17),
            "cycle_one_score": 51.5,
            "reconciliation_pause": False,
            "deferred_until": None,
        }

        result = await evaluate_rule_161(
            ticker="NBIS",
            current_friday_score=52.0,
            cycle_record=cycle_record,
            f12_no_fly_active=True,
            reconciliation_pending=False,
            session=mock_session,
        )

        assert result["status"] == "DEFERRED"
        assert result["trim_triggered"] is False
        assert result["deferred_reason"] == "F12_NO_FLY_ACTIVE"


# ---------------------------------------------------------------------------
# TestRule162GapDown
# ---------------------------------------------------------------------------


class TestRule162GapDown:
    """Rule 16.2: gap-down detection and 48-hour hold."""

    @pytest.mark.asyncio
    async def test_gap_exceeds_threshold_creates_hold(self) -> None:
        """Gap down > 20% → status HOLDING, hold_until set to 48 hours from open."""
        from atlas.services.section16_service import evaluate_rule_162

        open_price = Decimal("80.00")
        prev_close = Decimal("105.00")
        event_timestamp = datetime(2026, 4, 22, 9, 30, 0, tzinfo=timezone.utc)

        result = evaluate_rule_162(
            ticker="NBIS",
            prev_close=prev_close,
            open_price=open_price,
            event_timestamp=event_timestamp,
            gap_down_threshold_pct=Decimal("20"),
            hold_hours=48,
        )

        assert result["gap_triggered"] is True
        assert result["status"] == "HOLDING"
        assert result["gap_down_pct"] > Decimal("20")

    @pytest.mark.asyncio
    async def test_gap_below_threshold_not_triggered(self) -> None:
        """Gap down < 20% → not triggered."""
        from atlas.services.section16_service import evaluate_rule_162

        open_price = Decimal("90.00")
        prev_close = Decimal("105.00")
        event_timestamp = datetime(2026, 4, 22, 9, 30, 0, tzinfo=timezone.utc)

        result = evaluate_rule_162(
            ticker="NVDA",
            prev_close=prev_close,
            open_price=open_price,
            event_timestamp=event_timestamp,
            gap_down_threshold_pct=Decimal("20"),
            hold_hours=48,
        )

        assert result["gap_triggered"] is False
        assert result["status"] == "CLEAR"

    @pytest.mark.asyncio
    async def test_rescore_at_is_72_hours_after_event(self) -> None:
        """rescore_at must be event_timestamp + 72 hours."""
        from atlas.services.section16_service import evaluate_rule_162

        from datetime import timedelta

        open_price = Decimal("80.00")
        prev_close = Decimal("105.00")
        event_timestamp = datetime(2026, 4, 22, 9, 30, 0, tzinfo=timezone.utc)

        result = evaluate_rule_162(
            ticker="NBIS",
            prev_close=prev_close,
            open_price=open_price,
            event_timestamp=event_timestamp,
            gap_down_threshold_pct=Decimal("20"),
            hold_hours=48,
            rescore_hours=72,
        )

        expected_rescore = event_timestamp + timedelta(hours=72)
        assert result["rescore_at"] == expected_rescore


# ---------------------------------------------------------------------------
# TestRule163AppreciationTrim
# ---------------------------------------------------------------------------


class TestRule163AppreciationTrim:
    """Rule 16.3: concentration / appreciation trim rule."""

    def test_below_8pct_nav_no_action(self) -> None:
        """Position < 8% of NAV → CLEAR, no action."""
        from atlas.services.section16_service import evaluate_rule_163

        result = evaluate_rule_163(
            ticker="AVGO",
            position_value=Decimal("70000"),
            total_nav=Decimal("1000000"),
            soft_cap_pct=Decimal("8"),
            hard_cap_pct=Decimal("10"),
            trim_pct=Decimal("20"),
        )

        assert result["status"] == "CLEAR"
        assert result["no_new_capital"] is False
        assert result["consider_trim"] is False

    def test_above_8pct_triggers_no_new_capital(self) -> None:
        """Position 8–10% of NAV → NO_NEW_CAPITAL (soft cap breached)."""
        from atlas.services.section16_service import evaluate_rule_163

        result = evaluate_rule_163(
            ticker="AVGO",
            position_value=Decimal("85000"),
            total_nav=Decimal("1000000"),
            soft_cap_pct=Decimal("8"),
            hard_cap_pct=Decimal("10"),
            trim_pct=Decimal("20"),
        )

        assert result["status"] == "NO_NEW_CAPITAL"
        assert result["no_new_capital"] is True
        assert result["consider_trim"] is False

    def test_above_10pct_triggers_consider_trim(self) -> None:
        """Position > 10% of NAV → CONSIDER_TRIM with 20% trim size."""
        from atlas.services.section16_service import evaluate_rule_163

        result = evaluate_rule_163(
            ticker="AVGO",
            position_value=Decimal("110000"),
            total_nav=Decimal("1000000"),
            soft_cap_pct=Decimal("8"),
            hard_cap_pct=Decimal("10"),
            trim_pct=Decimal("20"),
        )

        assert result["status"] == "CONSIDER_TRIM"
        assert result["no_new_capital"] is True
        assert result["consider_trim"] is True
        assert result["trim_pct"] == Decimal("20")


# ---------------------------------------------------------------------------
# TestRule164PutProtection
# ---------------------------------------------------------------------------


class TestRule164PutProtection:
    """Rule 16.4: all-4-conditions protective put rule."""

    def test_all_four_conditions_met_recommends_puts(self) -> None:
        """When all 4 conditions are True, put protection is recommended."""
        from atlas.services.section16_service import evaluate_rule_164

        result = evaluate_rule_164(
            ticker="MU",
            bearish_flow_usd=Decimal("600000"),
            earnings_days_away=15,
            gain_from_cost_pct=Decimal("25"),
            current_score=65.0,
            put_flow_threshold_usd=Decimal("500000"),
            put_earnings_days=20,
            score_tier3_threshold=70,
        )

        assert result["recommend_puts"] is True
        assert result["conditions_met"] == 4
        assert result["status"] == "PUT_PROTECTION_RECOMMENDED"

    def test_flow_below_threshold_skips_puts(self) -> None:
        """bearish flow < $500K → condition 1 fails, puts not recommended."""
        from atlas.services.section16_service import evaluate_rule_164

        result = evaluate_rule_164(
            ticker="MU",
            bearish_flow_usd=Decimal("300000"),
            earnings_days_away=15,
            gain_from_cost_pct=Decimal("25"),
            current_score=65.0,
            put_flow_threshold_usd=Decimal("500000"),
            put_earnings_days=20,
            score_tier3_threshold=70,
        )

        assert result["recommend_puts"] is False
        assert result["conditions_met"] < 4

    def test_score_above_70_skips_puts(self) -> None:
        """Score ≥ 70 (Tier 2 or better) → condition 4 fails, puts not recommended."""
        from atlas.services.section16_service import evaluate_rule_164

        result = evaluate_rule_164(
            ticker="MU",
            bearish_flow_usd=Decimal("600000"),
            earnings_days_away=15,
            gain_from_cost_pct=Decimal("25"),
            current_score=72.0,
            put_flow_threshold_usd=Decimal("500000"),
            put_earnings_days=20,
            score_tier3_threshold=70,
        )

        assert result["recommend_puts"] is False
        assert result["status"] == "NOT_TRIGGERED"

    def test_missing_flow_data_returns_unknown(self) -> None:
        """When bearish_flow_usd is None → status UNKNOWN with missing source."""
        from atlas.services.section16_service import evaluate_rule_164

        result = evaluate_rule_164(
            ticker="MU",
            bearish_flow_usd=None,
            earnings_days_away=15,
            gain_from_cost_pct=Decimal("25"),
            current_score=65.0,
            put_flow_threshold_usd=Decimal("500000"),
            put_earnings_days=20,
            score_tier3_threshold=70,
        )

        assert result["recommend_puts"] is None
        assert result["status"] == "UNKNOWN"
        assert "F9" in result["missing_sources"]
