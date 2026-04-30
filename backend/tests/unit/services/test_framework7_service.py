"""Unit tests for Framework 7 — Earnings Gate Rule pure helpers.

Tests cover:
  - calculate_gate_close_date: 5 trading-day count-back, weekend skip
  - _evaluate_gate_logic: all four status branches with boundary conditions

All tests exercise pure functions only -- no I/O, no mocks required.
"""

from __future__ import annotations

from datetime import date

import pytest

from atlas.services.framework7_service import (
    _evaluate_gate_logic,
    calculate_gate_close_date,
)

# ---------------------------------------------------------------------------
# calculate_gate_close_date
# ---------------------------------------------------------------------------


class TestCalculateGateCloseDate:
    def test_april_29_earnings_gives_april_22(self) -> None:
        # April 29, 2026 (Wednesday) earnings
        # Count back 5 weekdays: Apr 28, Apr 27, Apr 24, Apr 23, Apr 22
        result = calculate_gate_close_date(date(2026, 4, 29))
        assert result == date(2026, 4, 22)

    def test_april_30_earnings_gives_april_23(self) -> None:
        # April 30, 2026 (Thursday) earnings
        # Count back 5 weekdays: Apr 29, Apr 28, Apr 27, Apr 24, Apr 23
        result = calculate_gate_close_date(date(2026, 4, 30))
        assert result == date(2026, 4, 23)

    def test_monday_earnings_skips_weekend(self) -> None:
        # Monday April 27, 2026 earnings
        # Count back: Apr 24(Fri)=1, Apr 23(Thu)=2, Apr 22(Wed)=3,
        #             Apr 21(Tue)=4, Apr 20(Mon)=5
        result = calculate_gate_close_date(date(2026, 4, 27))
        assert result == date(2026, 4, 20)

    def test_always_returns_a_weekday(self) -> None:
        result = calculate_gate_close_date(date(2026, 5, 20))
        # weekday() < 5 means Mon-Fri
        assert result.weekday() < 5

    def test_gate_close_strictly_before_earnings(self) -> None:
        earnings = date(2026, 4, 30)
        gate_close = calculate_gate_close_date(earnings)
        assert gate_close < earnings

    def test_exactly_five_weekdays_gap(self) -> None:
        earnings = date(2026, 4, 30)
        gate_close = calculate_gate_close_date(earnings)
        # Count weekdays between gate_close and earnings (exclusive of both)
        current = gate_close + __import__("datetime").timedelta(days=1)
        weekdays_between = 0
        while current < earnings:
            if current.weekday() < 5:
                weekdays_between += 1
            current += __import__("datetime").timedelta(days=1)
        # There should be exactly 4 weekdays between them (gate_close itself
        # is the 5th day back, so 4 weekdays lie between close and earnings)
        assert weekdays_between == 4


# ---------------------------------------------------------------------------
# _evaluate_gate_logic — OPEN (no earnings date)
# ---------------------------------------------------------------------------


class TestGateOpenNoEarnings:
    def test_status_is_open(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=None,
            final_score=65,
            insider_flag=False,
        )
        assert result.status == "OPEN"

    def test_can_add_is_true(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=None,
            final_score=65,
            insider_flag=False,
        )
        assert result.can_add is True

    def test_size_cap_is_full(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=None,
            final_score=65,
            insider_flag=False,
        )
        assert result.size_cap == pytest.approx(1.0)

    def test_gate_active_is_false(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=None,
            final_score=65,
            insider_flag=False,
        )
        assert result.gate_active is False

    def test_message_mentions_no_gate(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=None,
            final_score=65,
            insider_flag=False,
        )
        assert "no gate" in result.message.lower()


# ---------------------------------------------------------------------------
# _evaluate_gate_logic — OPEN (gate not yet active)
# ---------------------------------------------------------------------------


class TestGateOpenNotYetActive:
    """Gate close is in the future — earnings upcoming but gate not triggered."""

    def test_status_is_open(self) -> None:
        # TSEM earnings May 20; today = April 20 → gate not active
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=date(2026, 5, 20),
            final_score=70,
            insider_flag=False,
        )
        assert result.status == "OPEN"

    def test_gate_active_is_false(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=date(2026, 5, 20),
            final_score=70,
            insider_flag=False,
        )
        assert result.gate_active is False

    def test_can_add_is_true(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=date(2026, 5, 20),
            final_score=70,
            insider_flag=False,
        )
        assert result.can_add is True

    def test_gate_close_date_populated(self) -> None:
        result = _evaluate_gate_logic(
            ticker="TSEM",
            today=date(2026, 4, 20),
            earnings_date=date(2026, 5, 20),
            final_score=70,
            insider_flag=False,
        )
        assert result.gate_close_date is not None


# ---------------------------------------------------------------------------
# _evaluate_gate_logic — CLOSED (gate active, score <= 80)
# ---------------------------------------------------------------------------


class TestGateClosed:
    """Gate is active; score at or below 80 — no position adds."""

    def test_status_is_closed_score_below_80(self) -> None:
        # SNDK: earnings April 30, gate_close April 23, today April 24 (gate active)
        result = _evaluate_gate_logic(
            ticker="SNDK",
            today=date(2026, 4, 24),
            earnings_date=date(2026, 4, 30),
            final_score=75,
            insider_flag=False,
        )
        assert result.status == "CLOSED"

    def test_status_is_closed_score_exactly_80(self) -> None:
        # Score = 80 exactly → CLOSED (not 50% CAP — threshold is strictly above 80)
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=80,
            insider_flag=False,
        )
        assert result.status == "CLOSED"

    def test_can_add_is_false(self) -> None:
        result = _evaluate_gate_logic(
            ticker="SNDK",
            today=date(2026, 4, 24),
            earnings_date=date(2026, 4, 30),
            final_score=65,
            insider_flag=False,
        )
        assert result.can_add is False

    def test_size_cap_is_zero(self) -> None:
        result = _evaluate_gate_logic(
            ticker="SNDK",
            today=date(2026, 4, 24),
            earnings_date=date(2026, 4, 30),
            final_score=65,
            insider_flag=False,
        )
        assert result.size_cap == pytest.approx(0.0)

    def test_gate_active_is_true(self) -> None:
        result = _evaluate_gate_logic(
            ticker="SNDK",
            today=date(2026, 4, 24),
            earnings_date=date(2026, 4, 30),
            final_score=65,
            insider_flag=False,
        )
        assert result.gate_active is True


# ---------------------------------------------------------------------------
# _evaluate_gate_logic — 50% CAP (gate active, score > 80)
# ---------------------------------------------------------------------------


class TestGateCap50:
    """Gate is active; score above 80 — add permitted at 50% target weight."""

    def test_status_is_cap_50(self) -> None:
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=85,
            insider_flag=False,
        )
        assert result.status == "50% CAP"

    def test_can_add_is_true(self) -> None:
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=85,
            insider_flag=False,
        )
        assert result.can_add is True

    def test_size_cap_is_half(self) -> None:
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=85,
            insider_flag=False,
        )
        assert result.size_cap == pytest.approx(0.5)

    def test_score_81_triggers_cap(self) -> None:
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=81,
            insider_flag=False,
        )
        assert result.status == "50% CAP"

    def test_score_100_triggers_cap_not_uncapped(self) -> None:
        result = _evaluate_gate_logic(
            ticker="AAOI",
            today=date(2026, 4, 25),
            earnings_date=date(2026, 4, 30),
            final_score=100,
            insider_flag=False,
        )
        assert result.status == "50% CAP"
        assert result.size_cap == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# _evaluate_gate_logic — DOUBLE BLOCKED (gate active + insider_flag)
# ---------------------------------------------------------------------------


class TestGateDoubleBlocked:
    """Gate active AND insider_flag — blocked regardless of score."""

    def test_status_is_double_blocked(self) -> None:
        # NBIS: earnings April 29, insider_flag=True
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=85,
            insider_flag=True,
        )
        assert result.status == "DOUBLE BLOCKED"

    def test_double_blocked_overrides_high_score(self) -> None:
        # Even score = 100 → DOUBLE BLOCKED when insider_flag
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=100,
            insider_flag=True,
        )
        assert result.status == "DOUBLE BLOCKED"

    def test_can_add_is_false(self) -> None:
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=85,
            insider_flag=True,
        )
        assert result.can_add is False

    def test_size_cap_is_zero(self) -> None:
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=85,
            insider_flag=True,
        )
        assert result.size_cap == pytest.approx(0.0)

    def test_insider_flag_stored_in_response(self) -> None:
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=85,
            insider_flag=True,
        )
        assert result.insider_flag is True

    def test_double_blocked_also_low_score(self) -> None:
        # insider_flag + low score → DOUBLE BLOCKED (not just CLOSED)
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=55,
            insider_flag=True,
        )
        assert result.status == "DOUBLE BLOCKED"

    def test_days_to_earnings_populated(self) -> None:
        result = _evaluate_gate_logic(
            ticker="NBIS",
            today=date(2026, 4, 23),
            earnings_date=date(2026, 4, 29),
            final_score=85,
            insider_flag=True,
        )
        # April 29 - April 23 = 6 days
        assert result.days_to_earnings == 6

