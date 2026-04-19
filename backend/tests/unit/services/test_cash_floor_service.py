"""Unit tests for the Framework 5 Cash Floor service pure helpers.

Tests cover:
  - _floor_params_from_rule : rule string → (condition, min_pct, max_pct, rationale)
  - _floor_usd_amounts       : position value × floor percentages → USD bounds
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from atlas.services.cash_floor_service import (
    _floor_params_from_rule,
    _floor_usd_amounts,
)


# ---------------------------------------------------------------------------
# _floor_params_from_rule
# ---------------------------------------------------------------------------


class TestFloorParamsFromRule:
    def test_crisis_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CRISIS")
        assert condition == "CRISIS"

    def test_crisis_floor_min(self) -> None:
        _, floor_min, _, _ = _floor_params_from_rule("CRISIS")
        assert floor_min == pytest.approx(0.35)

    def test_crisis_floor_max(self) -> None:
        _, _, floor_max, _ = _floor_params_from_rule("CRISIS")
        assert floor_max == pytest.approx(0.40)

    def test_crisis_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CRISIS")
        assert "high beta protection" in rationale.lower()

    def test_caution_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CAUTION")
        assert condition == "CAUTION"

    def test_caution_floor_min(self) -> None:
        _, floor_min, _, _ = _floor_params_from_rule("CAUTION")
        assert floor_min == pytest.approx(0.25)

    def test_caution_floor_max(self) -> None:
        _, _, floor_max, _ = _floor_params_from_rule("CAUTION")
        assert floor_max == pytest.approx(0.35)

    def test_caution_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CAUTION")
        assert "T1" in rationale

    def test_clear_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("CLEAR")
        assert condition == "CLEAR"

    def test_clear_floor_min(self) -> None:
        _, floor_min, _, _ = _floor_params_from_rule("CLEAR")
        assert floor_min == pytest.approx(0.10)

    def test_clear_floor_max(self) -> None:
        _, _, floor_max, _ = _floor_params_from_rule("CLEAR")
        assert floor_max == pytest.approx(0.12)

    def test_clear_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("CLEAR")
        assert "macro buffer" in rationale.lower()

    def test_normal_condition(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("NORMAL")
        assert condition == "FULLY_DEPLOYED"

    def test_normal_floor_min_equals_max(self) -> None:
        _, floor_min, floor_max, _ = _floor_params_from_rule("NORMAL")
        assert floor_min == pytest.approx(floor_max)

    def test_normal_floor_value(self) -> None:
        _, floor_min, _, _ = _floor_params_from_rule("NORMAL")
        assert floor_min == pytest.approx(0.10)

    def test_normal_rationale(self) -> None:
        _, _, _, rationale = _floor_params_from_rule("NORMAL")
        assert "never" in rationale.lower()

    def test_unknown_rule_falls_back_to_fully_deployed(self) -> None:
        condition, _, _, _ = _floor_params_from_rule("UNKNOWN_REGIME")
        assert condition == "FULLY_DEPLOYED"


# ---------------------------------------------------------------------------
# _floor_usd_amounts
# ---------------------------------------------------------------------------


class TestFloorUsdAmounts:
    def test_crisis_position_10000(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("10000.00"), 0.35, 0.40)
        assert min_usd == Decimal("3500.00")
        assert max_usd == Decimal("4000.00")

    def test_clear_position_50000(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("50000.00"), 0.10, 0.12)
        assert min_usd == Decimal("5000.00")
        assert max_usd == Decimal("6000.00")

    def test_fully_deployed_floor_min_equals_max(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("20000.00"), 0.10, 0.10)
        assert min_usd == max_usd
        assert min_usd == Decimal("2000.00")

    def test_none_position_value_returns_none_bounds(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(None, 0.35, 0.40)
        assert min_usd is None
        assert max_usd is None

    def test_result_rounded_to_cents(self) -> None:
        # 333.33 * 0.35 = 116.6655 → should round to 116.67
        min_usd, _ = _floor_usd_amounts(Decimal("333.33"), 0.35, 0.40)
        assert min_usd is not None
        assert min_usd == Decimal("116.67")

    def test_zero_position_value(self) -> None:
        min_usd, max_usd = _floor_usd_amounts(Decimal("0.00"), 0.35, 0.40)
        assert min_usd == Decimal("0.00")
        assert max_usd == Decimal("0.00")
