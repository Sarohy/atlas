"""Unit tests for OptionsFlowService pure helpers.

TDD — covers deterministic pure functions (no I/O).

Pure functions under test:
  _derive_dark_pool_direction — call_premium/put_premium → 'BULLISH'|'BEARISH'|'NEUTRAL'
  _build_response             — DarkPoolIndicator.direction is populated from call/put
"""

from __future__ import annotations

import pytest

from atlas.services.options_flow_service import (
    _build_response,
    _derive_dark_pool_direction,
)


# ---------------------------------------------------------------------------
# _derive_dark_pool_direction
# ---------------------------------------------------------------------------


class TestDeriveDarkPoolDirection:
    """Direction is inferred from call_premium vs put_premium ratio.

    Thresholds mirror F9's uw_direction derivation:
      ratio > 1.5  → BULLISH
      ratio < 0.67 → BEARISH   (inverse of 1.5)
      otherwise    → NEUTRAL
    """

    def test_bullish_when_calls_dominate(self) -> None:
        assert _derive_dark_pool_direction(300_000.0, 100_000.0) == "BULLISH"

    def test_bullish_at_boundary(self) -> None:
        # ratio = 1.5 exactly → BULLISH
        assert _derive_dark_pool_direction(150_000.0, 100_000.0) == "BULLISH"

    def test_bearish_when_puts_dominate(self) -> None:
        # ratio = 0.5 → BEARISH
        assert _derive_dark_pool_direction(50_000.0, 100_000.0) == "BEARISH"

    def test_bearish_at_boundary(self) -> None:
        # ratio ~ 0.67 → BEARISH
        assert _derive_dark_pool_direction(66_666.0, 100_000.0) == "BEARISH"

    def test_neutral_when_balanced(self) -> None:
        # ratio ~ 1.0
        assert _derive_dark_pool_direction(100_000.0, 100_000.0) == "NEUTRAL"

    def test_neutral_when_calls_none(self) -> None:
        assert _derive_dark_pool_direction(None, 100_000.0) == "NEUTRAL"

    def test_neutral_when_puts_none(self) -> None:
        assert _derive_dark_pool_direction(100_000.0, None) == "NEUTRAL"

    def test_neutral_when_both_none(self) -> None:
        assert _derive_dark_pool_direction(None, None) == "NEUTRAL"

    def test_neutral_when_puts_zero(self) -> None:
        # Avoid division by zero
        assert _derive_dark_pool_direction(100_000.0, 0.0) == "NEUTRAL"


# ---------------------------------------------------------------------------
# DarkPoolIndicator.direction populated by _build_response
# ---------------------------------------------------------------------------


class TestBuildResponseDarkPoolDirection:
    """_build_response must populate DarkPoolIndicator.direction."""

    def test_direction_bullish_when_calls_dominate(self) -> None:
        result = _build_response(
            ticker="TEST",
            largest_premium=500_000.0,
            call_premium=300_000.0,
            put_premium=100_000.0,
            call_volume=1000.0,
            call_oi=500.0,
            largest_dark_pool=200_000.0,
            total_dark_pool=500_000.0,
            dark_pool_count=5,
            has_golden_sweep=False,
            has_single_sweep=False,
            has_repeated_hits=False,
            sweep_premium=None,
            collar_flag=False,
        )
        assert result.dark_pool.direction == "BULLISH"

    def test_direction_bearish_when_puts_dominate(self) -> None:
        result = _build_response(
            ticker="TEST",
            largest_premium=200_000.0,
            call_premium=50_000.0,
            put_premium=200_000.0,
            call_volume=None,
            call_oi=None,
            largest_dark_pool=None,
            total_dark_pool=None,
            dark_pool_count=0,
            has_golden_sweep=False,
            has_single_sweep=False,
            has_repeated_hits=False,
            sweep_premium=None,
            collar_flag=False,
        )
        assert result.dark_pool.direction == "BEARISH"

    def test_direction_neutral_when_no_premium_data(self) -> None:
        result = _build_response(
            ticker="TEST",
            largest_premium=None,
            call_premium=None,
            put_premium=None,
            call_volume=None,
            call_oi=None,
            largest_dark_pool=None,
            total_dark_pool=None,
            dark_pool_count=0,
            has_golden_sweep=False,
            has_single_sweep=False,
            has_repeated_hits=False,
            sweep_premium=None,
            collar_flag=False,
        )
        assert result.dark_pool.direction == "NEUTRAL"
