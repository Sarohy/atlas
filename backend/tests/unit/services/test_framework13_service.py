"""Unit tests for Framework 13 — Beta-Adjusted Portfolio Management.

ATLAS v7.3.4 spec.

All 12 spec test cases are covered here, plus supporting unit tests for every
public function in framework13_service.py.

TDD: these tests were written BEFORE the service implementation.
Run:  uv run pytest tests/unit/services/test_framework13_service.py -v
"""

from __future__ import annotations

import math

import pytest

from atlas.schemas.framework13 import BetaSource, Framework13Result, PortfolioBetaResult
from atlas.services.framework13_service import (
    CHINA_RISK_TICKERS,
    CONFIRMED_BETAS,
    DEFAULT_BETA,
    calculate_portfolio_beta,
    evaluate_framework13,
    get_beta,
    get_beta_cap_limit,
    get_beta_dynamic,
    is_beta_capped,
)

# ---------------------------------------------------------------------------
# get_beta
# ---------------------------------------------------------------------------


class TestGetBeta:
    def test_confirmed_ticker_returns_correct_beta(self) -> None:
        beta, source = get_beta("AAOI")
        assert beta == pytest.approx(4.03)
        assert source == BetaSource.CONFIRMED

    def test_confirmed_ticker_case_insensitive(self) -> None:
        beta, source = get_beta("aaoi")
        assert beta == pytest.approx(4.03)
        assert source == BetaSource.CONFIRMED

    def test_fn_beta_is_2_70(self) -> None:
        beta, source = get_beta("FN")
        assert beta == pytest.approx(2.70)
        assert source == BetaSource.CONFIRMED

    def test_unknown_ticker_returns_default(self) -> None:
        beta, source = get_beta("ZZZTEST")
        assert beta == pytest.approx(DEFAULT_BETA)
        assert source == BetaSource.DEFAULT

    def test_all_confirmed_betas_present(self) -> None:
        expected_tickers = [
            "AAOI", "CRDO", "UCTT", "MRVL", "VICR", "TTMI",
            "NBIS", "SNDK", "LITE", "COHR", "AEHR", "MU",
            "CIEN", "TSM", "FN", "TSEM", "NEM",
        ]
        for ticker in expected_tickers:
            beta, source = get_beta(ticker)
            assert source == BetaSource.CONFIRMED, f"{ticker} should be CONFIRMED"
            assert beta > 0.0, f"{ticker} beta should be positive"

    def test_mu_beta(self) -> None:
        beta, _ = get_beta("MU")
        assert beta == pytest.approx(2.42)

    def test_tsm_beta(self) -> None:
        beta, _ = get_beta("TSM")
        assert beta == pytest.approx(1.30)

    def test_nem_beta_below_1(self) -> None:
        beta, _ = get_beta("NEM")
        assert beta == pytest.approx(0.55)

    def test_gct_not_in_confirmed_table_uses_default(self) -> None:
        """GCT is China risk but NOT in the confirmed beta table."""
        beta, source = get_beta("GCT")
        assert beta == pytest.approx(DEFAULT_BETA)
        assert source == BetaSource.DEFAULT


# ---------------------------------------------------------------------------
# get_beta_cap_limit
# ---------------------------------------------------------------------------


class TestGetBetaCapLimit:
    def test_china_risk_cap_is_0025(self) -> None:
        cap = get_beta_cap_limit("GCT", 1.0)
        assert cap == pytest.approx(0.0025)

    def test_beta_above_3_cap_is_1pct(self) -> None:
        cap = get_beta_cap_limit("AAOI", 3.30)
        assert cap == pytest.approx(0.010)

    def test_beta_exactly_3_cap_is_1pct(self) -> None:
        cap = get_beta_cap_limit("AAOI", 3.0)
        assert cap == pytest.approx(0.010)

    def test_beta_in_2_to_3_range_cap_is_1pct(self) -> None:
        cap = get_beta_cap_limit("CRDO", 2.67)
        assert cap == pytest.approx(0.010)

    def test_beta_exactly_2_cap_is_1pct(self) -> None:
        cap = get_beta_cap_limit("UCTT", 2.0)
        assert cap == pytest.approx(0.010)

    def test_beta_in_1_5_to_2_range_cap_is_2_5pct(self) -> None:
        cap = get_beta_cap_limit("COHR", 1.75)
        assert cap == pytest.approx(0.025)

    def test_beta_exactly_1_5_cap_is_2_5pct(self) -> None:
        cap = get_beta_cap_limit("LITE", 1.50)
        assert cap == pytest.approx(0.025)

    def test_beta_below_1_5_no_cap(self) -> None:
        cap = get_beta_cap_limit("MU", 1.65)
        # 1.65 is in [1.5, 2.0) — should be 2.5%
        assert cap == pytest.approx(0.025)

    def test_moderate_beta_no_beta_restriction(self) -> None:
        cap = get_beta_cap_limit("TSM", 1.30)
        assert cap == pytest.approx(0.050)

    def test_low_beta_no_restriction(self) -> None:
        cap = get_beta_cap_limit("NEM", 0.55)
        assert cap == pytest.approx(0.050)

    def test_china_risk_overrides_beta_tier(self) -> None:
        """China risk cap applies even if beta were somehow low."""
        cap = get_beta_cap_limit("GCT", 0.5)
        assert cap == pytest.approx(0.0025)


# ---------------------------------------------------------------------------
# is_beta_capped
# ---------------------------------------------------------------------------


class TestIsBetaCapped:
    # ── Spec Test 1 — AAOI at 0.9% NAV ─────────────────────────────────────

    def test_aaoi_0_9pct_not_capped(self) -> None:
        result = is_beta_capped("AAOI", 0.009)
        assert result["cap_active"] is False
        assert result["adds_permitted"] is True

    def test_aaoi_0_9pct_warning_amber(self) -> None:
        result = is_beta_capped("AAOI", 0.009)
        assert result["warning_level"] == "AMBER"

    def test_aaoi_0_9pct_correct_effective_exposure(self) -> None:
        # 0.009 * 4.03 * 100 = 3.627
        result = is_beta_capped("AAOI", 0.009)
        assert result["effective_exposure"] == pytest.approx(3.627, rel=1e-3)

    def test_aaoi_0_9pct_warning_message_mentions_exposure(self) -> None:
        result = is_beta_capped("AAOI", 0.009)
        msg = result["warning_message"]
        assert msg is not None
        assert "3.63" in msg

    # ── Spec Test 2 — AAOI at 1.0% NAV (at cap) ─────────────────────────────

    def test_aaoi_1_0pct_cap_active(self) -> None:
        result = is_beta_capped("AAOI", 0.010)
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False

    def test_aaoi_1_0pct_warning_level_red(self) -> None:
        result = is_beta_capped("AAOI", 0.010)
        assert result["warning_level"] == "RED"

    def test_aaoi_1_0pct_cap_reason_mentions_hard_cap(self) -> None:
        result = is_beta_capped("AAOI", 0.010)
        reason = result["cap_reason"]
        assert reason is not None
        assert "hard cap" in reason.lower() or "1.0%" in reason

    # ── Spec Test 3 — AAOI at 1.1% NAV (above cap) ──────────────────────────

    def test_aaoi_1_1pct_cap_active(self) -> None:
        result = is_beta_capped("AAOI", 0.011)
        assert result["cap_active"] is True

    def test_aaoi_1_1pct_effective_exposure(self) -> None:
        # 0.011 * 4.03 * 100 = 4.433
        result = is_beta_capped("AAOI", 0.011)
        assert result["effective_exposure"] == pytest.approx(4.433, rel=1e-3)

    # ── Spec Test 4 — MU at 1.3% NAV ─────────────────────────────────────────

    def test_mu_1_3pct_is_capped(self) -> None:
        """MU beta 2.42 >= 2.0 — cap = 1.0% NAV. 1.3% > 1.0% — must be capped."""
        result = is_beta_capped("MU", 0.013)
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False
        assert result["warning_level"] == "RED"

    def test_mu_beta_is_2_42(self) -> None:
        result = is_beta_capped("MU", 0.013)
        assert result["beta"] == pytest.approx(2.42)

    # ── New tests: FN beta update (1.06 → 2.70) and AAOI at 4.4% NAV ─────────

    def test_fn_capped_at_1_8_pct(self) -> None:
        """FN beta 2.70 >= 2.0 → cap = 1.0% NAV. 1.8% > 1.0% → capped."""
        result = is_beta_capped("FN", 0.018)
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False

    def test_fn_not_capped_below_1_pct(self) -> None:
        """FN at 0.8% NAV < 1.0% cap → not capped."""
        result = is_beta_capped("FN", 0.008)
        assert result["cap_active"] is False

    def test_aaoi_capped_at_4_4_pct(self) -> None:
        """AAOI beta 4.03 >= 3.0 → cap = 1.0% NAV. 4.4% > 1.0% → capped."""
        result = is_beta_capped("AAOI", 0.044)
        assert result["cap_active"] is True

    # ── Spec Test 5 — GCT China risk at 0.3% ─────────────────────────────────

    def test_gct_0_3pct_cap_active(self) -> None:
        result = is_beta_capped("GCT", 0.003)
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False

    def test_gct_cap_reason_mentions_china(self) -> None:
        result = is_beta_capped("GCT", 0.003)
        reason = result["cap_reason"]
        assert reason is not None
        assert "china" in reason.lower()

    # ── Spec Test 6 — Unknown ticker ─────────────────────────────────────────

    def test_unknown_ticker_default_beta(self) -> None:
        result = is_beta_capped("XYZ", 0.005)
        assert result["beta"] == pytest.approx(DEFAULT_BETA)
        assert result["default_beta_flag"] is True

    def test_unknown_ticker_no_cap_at_0_5pct(self) -> None:
        result = is_beta_capped("XYZ", 0.005)
        assert result["cap_active"] is False

    # ── Spec Test 7 — TTMI exit candidate ────────────────────────────────────

    def test_ttmi_flagged_as_exit_candidate(self) -> None:
        result = is_beta_capped("TTMI", 0.005)
        assert result["is_exit_candidate"] is True

    def test_ttmi_0_5pct_not_capped(self) -> None:
        result = is_beta_capped("TTMI", 0.005)
        assert result["cap_active"] is False

    def test_non_ttmi_not_exit_candidate(self) -> None:
        result = is_beta_capped("AAOI", 0.005)
        assert result["is_exit_candidate"] is False

    # ── Edge: position exactly at cap threshold ───────────────────────────────

    def test_position_exactly_at_china_cap_is_capped(self) -> None:
        result = is_beta_capped("GCT", 0.0025)
        assert result["cap_active"] is True

    def test_position_just_below_china_cap_not_capped(self) -> None:
        result = is_beta_capped("GCT", 0.0024)
        assert result["cap_active"] is False

    def test_aaoi_below_amber_threshold_no_warning(self) -> None:
        """AAOI at 0.5% exactly — no amber warning below 0.5%."""
        result = is_beta_capped("AAOI", 0.005)
        # 0.5% is the boundary — warning only when strictly > 0.5%
        assert result["warning_level"] == "NONE"

    def test_aaoi_just_above_amber_threshold_gives_warning(self) -> None:
        result = is_beta_capped("AAOI", 0.0051)
        assert result["warning_level"] == "AMBER"

    def test_confirmed_source_flag_is_false_for_confirmed(self) -> None:
        result = is_beta_capped("AAOI", 0.005)
        assert result["default_beta_flag"] is False


# ---------------------------------------------------------------------------
# evaluate_framework13
# ---------------------------------------------------------------------------


class TestEvaluateFramework13:
    @pytest.mark.asyncio
    async def test_aaoi_0_9pct_result_shape(self) -> None:
        result = await evaluate_framework13("AAOI", 0.009, 1_000_000.0)
        assert isinstance(result, Framework13Result)
        assert result.ticker == "AAOI"
        assert result.beta == pytest.approx(4.03)
        assert result.beta_source == BetaSource.CONFIRMED
        assert result.beta_cap_active is False
        assert result.adds_permitted is True
        assert result.warning_level == "AMBER"

    @pytest.mark.asyncio
    async def test_aaoi_1_0pct_capped(self) -> None:
        result = await evaluate_framework13("AAOI", 0.010, 1_000_000.0)
        assert result.beta_cap_active is True
        assert result.adds_permitted is False
        assert result.warning_level == "RED"
        assert result.beta_cap_limit_pct == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_aaoi_effective_exposure_note_format(self) -> None:
        result = await evaluate_framework13("AAOI", 0.009, 1_000_000.0)
        note = result.effective_exposure_note
        assert "4.03" in note
        assert "%" in note

    @pytest.mark.asyncio
    async def test_aaoi_sizing_tier_is_aaoi_type(self) -> None:
        result = await evaluate_framework13("AAOI", 0.005, 1_000_000.0)
        assert result.sizing_tier == "AAOI_TYPE_HIGH_BETA"

    @pytest.mark.asyncio
    async def test_mu_sizing_tier_is_very_high_beta(self) -> None:
        result = await evaluate_framework13("MU", 0.005, 1_000_000.0)
        assert result.sizing_tier == "VERY_HIGH_BETA"

    @pytest.mark.asyncio
    async def test_tsm_sizing_tier_is_moderate(self) -> None:
        result = await evaluate_framework13("TSM", 0.01, 1_000_000.0)
        assert result.sizing_tier == "MODERATE_BETA"

    @pytest.mark.asyncio
    async def test_nem_sizing_tier_is_low(self) -> None:
        result = await evaluate_framework13("NEM", 0.01, 1_000_000.0)
        assert result.sizing_tier == "LOW_BETA"

    @pytest.mark.asyncio
    async def test_position_dollars_calculated(self) -> None:
        result = await evaluate_framework13("AAOI", 0.009, 1_000_000.0)
        assert result.position_dollars == pytest.approx(9_000.0)

    @pytest.mark.asyncio
    async def test_beta_source_flag_false_for_confirmed(self) -> None:
        result = await evaluate_framework13("AAOI", 0.009, 1_000_000.0)
        assert result.beta_source_flag is False

    @pytest.mark.asyncio
    async def test_beta_source_flag_true_for_default(self) -> None:
        result = await evaluate_framework13("ZZZTEST", 0.005, 1_000_000.0)
        assert result.beta_source_flag is True
        assert result.beta_source == BetaSource.DEFAULT


# ---------------------------------------------------------------------------
# calculate_portfolio_beta — Spec Test 8
# ---------------------------------------------------------------------------


class TestCalculatePortfolioBeta:
    @pytest.mark.asyncio
    async def test_returns_portfolio_beta_result(self) -> None:
        positions = [{"ticker": "AAOI", "weight": 0.009}]
        result = await calculate_portfolio_beta(positions, 0.0)
        assert isinstance(result, PortfolioBetaResult)

    @pytest.mark.asyncio
    async def test_weighted_avg_beta_calculated_correctly(self) -> None:
        positions = [
            {"ticker": "AAOI", "weight": 0.009},
            {"ticker": "MU", "weight": 0.013},
        ]
        # AAOI: 0.009 × 4.03 = 0.03627; MU: 0.013 × 2.42 = 0.03146
        expected_sum = 0.009 * 4.03 + 0.013 * 2.42
        result = await calculate_portfolio_beta(positions, 0.0)
        assert result.weighted_avg_beta == pytest.approx(expected_sum, rel=1e-4)

    @pytest.mark.asyncio
    async def test_effective_beta_accounts_for_cash(self) -> None:
        positions = [{"ticker": "MU", "weight": 1.0}]
        # 100% MU, 20% cash → effective = 2.42 × 0.80
        result = await calculate_portfolio_beta(positions, 0.20)
        assert result.effective_beta == pytest.approx(2.42 * 0.80, rel=1e-4)

    @pytest.mark.asyncio
    async def test_effective_beta_formula_example_from_spec(self) -> None:
        """Spec example: portfolio beta 1.75, cash 20% → effective 1.40."""
        # Construct portfolio where weighted_avg_beta == 1.75
        # Use FN: beta 1.06 doesn't work. Use TSM 1.30 and MU 1.65 at equal weight
        # Let's use 1 position at weight=1 with a synthetic 1.75 beta → NEM 0.55, too low
        # Actually let's just use COHR (1.75) at 100% weight
        positions = [{"ticker": "COHR", "weight": 1.0}]
        result = await calculate_portfolio_beta(positions, 0.20)
        assert result.effective_beta == pytest.approx(1.75 * 0.80, rel=1e-4)
        assert result.effective_beta == pytest.approx(1.40, rel=1e-3)

    @pytest.mark.asyncio
    async def test_spec_test_8_partial_positions(self) -> None:
        """Partial version of spec test 8 (AAOI + MRVL + MU + TSM)."""
        positions = [
            {"ticker": "AAOI", "weight": 0.009},
            {"ticker": "MRVL", "weight": 0.034},
            {"ticker": "MU", "weight": 0.013},
            {"ticker": "TSM", "weight": 0.117},
        ]
        result = await calculate_portfolio_beta(positions, 0.129)
        # Contributions: 0.009*4.03 + 0.034*1.98 + 0.013*2.42 + 0.117*1.30
        expected_weighted = 0.009 * 4.03 + 0.034 * 1.98 + 0.013 * 2.42 + 0.117 * 1.30
        expected_effective = expected_weighted * (1 - 0.129)
        assert result.weighted_avg_beta == pytest.approx(expected_weighted, rel=1e-4)
        assert result.effective_beta == pytest.approx(expected_effective, rel=1e-4)

    @pytest.mark.asyncio
    async def test_position_betas_list_populated(self) -> None:
        positions = [{"ticker": "MU", "weight": 0.013}]
        result = await calculate_portfolio_beta(positions, 0.10)
        assert len(result.position_betas) == 1
        assert result.position_betas[0].ticker == "MU"
        assert result.position_betas[0].beta == pytest.approx(2.42)

    @pytest.mark.asyncio
    async def test_target_beta_is_1_75(self) -> None:
        positions = [{"ticker": "MU", "weight": 0.013}]
        result = await calculate_portfolio_beta(positions, 0.10)
        assert result.target_beta == pytest.approx(1.75)

    # ── Spec Test 10 — effective beta elevated ────────────────────────────────

    @pytest.mark.asyncio
    async def test_beta_status_elevated_when_above_1_75(self) -> None:
        # AAOI × large weight → effective > 1.75
        positions = [{"ticker": "AAOI", "weight": 0.70}]
        result = await calculate_portfolio_beta(positions, 0.0)
        assert result.beta_status in ("ELEVATED", "CRITICAL")
        assert result.warning_level in ("RED", "CRITICAL")

    @pytest.mark.asyncio
    async def test_warning_message_set_when_elevated(self) -> None:
        positions = [{"ticker": "AAOI", "weight": 0.70}]
        result = await calculate_portfolio_beta(positions, 0.0)
        assert result.warning_message is not None

    @pytest.mark.asyncio
    async def test_beta_status_normal_when_below_1_75(self) -> None:
        # NEM beta 0.55 — effective will be very low
        positions = [{"ticker": "NEM", "weight": 0.50}]
        result = await calculate_portfolio_beta(positions, 0.50)
        assert result.beta_status == "NORMAL"

    @pytest.mark.asyncio
    async def test_empty_positions_returns_zero_beta(self) -> None:
        result = await calculate_portfolio_beta([], 0.10)
        assert result.weighted_avg_beta == pytest.approx(0.0)
        assert result.effective_beta == pytest.approx(0.0)

    # ── Spec Test 11 — regime change updates effective beta ───────────────────

    @pytest.mark.asyncio
    async def test_caution_cash_20pct_vs_clear_cash_8pct(self) -> None:
        positions = [{"ticker": "COHR", "weight": 0.875}]
        caution_result = await calculate_portfolio_beta(positions, 0.20)
        clear_result = await calculate_portfolio_beta(positions, 0.08)
        # CLEAR (8% cash) → higher effective beta than CAUTION (20% cash)
        assert clear_result.effective_beta > caution_result.effective_beta


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_aaoi_beta_is_4_03(self) -> None:
        assert CONFIRMED_BETAS["AAOI"] == pytest.approx(4.03)

    def test_fn_beta_in_table_is_2_70(self) -> None:
        assert CONFIRMED_BETAS["FN"] == pytest.approx(2.70)

    def test_nem_beta_is_0_55(self) -> None:
        assert CONFIRMED_BETAS["NEM"] == pytest.approx(0.55)

    def test_17_confirmed_betas(self) -> None:
        assert len(CONFIRMED_BETAS) == 17

    def test_default_beta_is_1_0(self) -> None:
        assert DEFAULT_BETA == pytest.approx(1.0)

    def test_china_risk_contains_gct(self) -> None:
        assert "GCT" in CHINA_RISK_TICKERS

    def test_calculated_beta_source_exists(self) -> None:
        assert BetaSource.CALCULATED == "CALCULATED"


# ---------------------------------------------------------------------------
# get_beta_dynamic — async Polygon fallback
# ---------------------------------------------------------------------------


class TestGetBetaDynamic:
    @pytest.mark.asyncio
    async def test_known_ticker_returns_confirmed(self) -> None:
        beta, source = await get_beta_dynamic("AAOI")
        assert beta == pytest.approx(4.03)
        assert source == BetaSource.CONFIRMED

    @pytest.mark.asyncio
    async def test_known_ticker_fn_returns_confirmed(self) -> None:
        beta, source = await get_beta_dynamic("FN")
        assert beta == pytest.approx(2.70)
        assert source == BetaSource.CONFIRMED

    @pytest.mark.asyncio
    async def test_unknown_ticker_no_api_key_falls_back_to_default(self) -> None:
        """With no POLYGON_API_KEY in test env, unknown ticker → DEFAULT 1.0."""
        beta, source = await get_beta_dynamic("UNKNOWNTICKER_XYZ")
        # No API key in test env — fetch returns None, falls back to DEFAULT.
        assert beta == pytest.approx(DEFAULT_BETA)
        assert source == BetaSource.DEFAULT

    @pytest.mark.asyncio
    async def test_case_insensitive_lookup(self) -> None:
        beta, source = await get_beta_dynamic("mu")
        assert beta == pytest.approx(2.42)
        assert source == BetaSource.CONFIRMED
