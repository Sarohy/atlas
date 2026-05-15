"""Unit tests for Framework 29 — Capitulation / Re-Entry AND Gate service.

Tests exercise pure (I/O-free) signal helpers only.
Async fetcher functions and the full evaluation loop are covered by integration
tests that inject mock httpx clients.

Updated signal spec (2026-05-14):
  1. VIX touches prior regime-high then declines ≥3 consecutive sessions
  2. Regime modifier is CAUTION — market stress confirms capitulation dynamics
  3. Put/call ratio spikes above 1.3 then reverses downward
  4. S&P 500 breadth computed from Polygon components: dips below 30% then recovers
  [S5 removed — CRISIS HALT is now a hard stop, not a confirming signal]

Gate rule: 3 of 4 confirmed = GREEN LIGHT
CRISIS HALT regime blocks F29 regardless of signal count.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.schemas.framework29 import SignalStatus
from atlas.services.framework29_service import (
    _BREADTH_MIN_VALID_TICKERS,
    _BREADTH_WASHOUT_THRESHOLD,
    _PCR_PANIC_THRESHOLD,
    _REGIME_CAUTION_LABEL,
    _VIX_DECLINE_SESSIONS,
    _VIX_REGIME_WINDOW,
    _check_signal1_vix,
    _check_signal2_regime,
    _check_signal3_pcr,
    _check_signal4_breadth,
    _compute_breadth_pct_series,
    _determine_gate_status,
    _fetch_sp500_breadth_series,
    _find_regime_high,
)


# ---------------------------------------------------------------------------
# _find_regime_high
# ---------------------------------------------------------------------------


class TestFindRegimeHigh:
    def test_returns_max_in_window(self) -> None:
        closes = [20.0, 18.0, 25.0, 22.0, 30.0, 28.0]
        assert _find_regime_high(closes, window=3) == 30.0

    def test_returns_none_when_not_enough_data(self) -> None:
        assert _find_regime_high([10.0, 20.0], window=5) is None

    def test_exact_window_size(self) -> None:
        closes = [5.0, 10.0, 8.0]
        assert _find_regime_high(closes, window=3) == 10.0


# ---------------------------------------------------------------------------
# Signal 1 — VIX regime-high + 3-session decline
# ---------------------------------------------------------------------------


class TestSignal1Vix:
    def _make_closes(self, regime_high: float, tail: list[float]) -> list[float]:
        """Build a synthetic VIX series that touches regime_high then ends with tail."""
        # Enough padding so regime window finds the high and tail is at the end.
        padding = [15.0] * (_VIX_REGIME_WINDOW - len(tail) - 1)
        return padding + [regime_high] + tail

    def test_confirmed_when_touched_high_and_declining(self) -> None:
        # Tail of 4 values (3 declines: 24→22→20→18)
        closes = self._make_closes(regime_high=24.0, tail=[24.0, 22.0, 20.0, 18.0])
        status, vals = _check_signal1_vix(closes)
        assert status == SignalStatus.CONFIRMED
        assert vals["vix_currently_declining"] is True
        assert vals["vix_touched_regime_high"] is True

    def test_not_met_when_vix_still_rising(self) -> None:
        # Tail is rising — no decline
        closes = self._make_closes(regime_high=24.0, tail=[24.0, 22.0, 23.0, 25.0])
        status, vals = _check_signal1_vix(closes)
        assert status == SignalStatus.NOT_MET
        assert vals["vix_currently_declining"] is False

    def test_not_met_when_peak_too_recent(self) -> None:
        # Peak is the most recent session — sessions_since_peak = 0 < 3 → not touched yet
        closes = [15.0] * (_VIX_REGIME_WINDOW - 1) + [30.0]  # 30.0 is latest, just spiked
        status, vals = _check_signal1_vix(closes)
        assert status == SignalStatus.NOT_MET
        assert vals["vix_touched_regime_high"] is False

    def test_unavailable_when_insufficient_data(self) -> None:
        status, vals = _check_signal1_vix([20.0, 18.0])
        assert status == SignalStatus.UNAVAILABLE
        assert "reason" in vals

    def test_confirmed_when_peak_exactly_at_decline_sessions_ago(self) -> None:
        # Peak is exactly _VIX_DECLINE_SESSIONS sessions ago — minimum valid case
        # Series: [15]*16 + [30.0] + [28.0, 26.0, 24.0] = 20 values
        # Peak at index 16, sessions_since_peak = 3 = _VIX_DECLINE_SESSIONS → touched = True
        closes = [15.0] * (_VIX_REGIME_WINDOW - _VIX_DECLINE_SESSIONS - 1) + [30.0] + [28.0, 26.0, 24.0]
        status, vals = _check_signal1_vix(closes)
        assert status == SignalStatus.CONFIRMED
        assert vals["vix_touched_regime_high"] is True
        assert vals["sessions_since_peak"] == _VIX_DECLINE_SESSIONS


# ---------------------------------------------------------------------------
# Signal 2 — Regime modifier is CAUTION (replaces Brent oil signal)
# ---------------------------------------------------------------------------


class TestSignal2Regime:
    def test_confirmed_when_caution(self) -> None:
        status, vals = _check_signal2_regime("CAUTION")
        assert status == SignalStatus.CONFIRMED
        assert vals["confirmed"] is True

    def test_not_met_when_soft_caution(self) -> None:
        status, vals = _check_signal2_regime("SOFT CAUTION")
        assert status == SignalStatus.NOT_MET
        assert vals["confirmed"] is False

    def test_not_met_when_clear(self) -> None:
        status, vals = _check_signal2_regime("CLEAR")
        assert status == SignalStatus.NOT_MET
        assert vals["confirmed"] is False

    def test_unavailable_when_none(self) -> None:
        status, vals = _check_signal2_regime(None)
        assert status == SignalStatus.UNAVAILABLE
        assert "reason" in vals

    def test_not_met_when_crisis_halt_safety_path(self) -> None:
        # CRISIS_HALT should not reach S2 (hard stop fires first), but if it
        # somehow does, S2 returns NOT_MET rather than CONFIRMED.
        status, vals = _check_signal2_regime("CRISIS HALT")
        assert status == SignalStatus.NOT_MET

    def test_regime_label_present_in_output(self) -> None:
        _, vals = _check_signal2_regime("CAUTION")
        assert vals["regime_label"] == "CAUTION"

    def test_constant_value(self) -> None:
        assert _REGIME_CAUTION_LABEL == "CAUTION"

    def test_case_normalised(self) -> None:
        # lowercase input should still confirm
        status, _ = _check_signal2_regime("caution")
        assert status == SignalStatus.CONFIRMED


# ---------------------------------------------------------------------------
# Signal 3 — Put/call ratio spikes above 1.3 then reverses
# ---------------------------------------------------------------------------


class TestSignal3PCR:
    def test_confirmed_when_spiked_and_reversing(self) -> None:
        # PCR was 1.35 (above panic threshold), now falling: 1.35 → 1.20
        pcr = [1.0, 1.05, 1.35, 1.20]
        status, vals = _check_signal3_pcr(pcr)
        assert status == SignalStatus.CONFIRMED
        assert vals["spike_detected_in_window"] is True
        assert vals["currently_reversing"] is True

    def test_not_met_when_spike_present_but_still_rising(self) -> None:
        pcr = [1.0, 1.35, 1.40]  # still rising after spike
        status, vals = _check_signal3_pcr(pcr)
        assert status == SignalStatus.NOT_MET
        assert vals["currently_reversing"] is False

    def test_not_met_when_reversing_but_never_spiked(self) -> None:
        pcr = [1.10, 1.20, 1.25, 1.15]  # declining but never hit panic threshold
        status, vals = _check_signal3_pcr(pcr)
        assert status == SignalStatus.NOT_MET
        assert vals["spike_detected_in_window"] is False

    def test_not_met_when_pcr_flat(self) -> None:
        pcr = [1.0, 1.35, 1.35]  # latest == previous (not reversing)
        status, vals = _check_signal3_pcr(pcr)
        assert status == SignalStatus.NOT_MET

    def test_unavailable_when_too_few_sessions(self) -> None:
        status, vals = _check_signal3_pcr([1.35])
        assert status == SignalStatus.UNAVAILABLE
        assert "reason" in vals

    def test_exactly_at_panic_threshold_qualifies_as_spike(self) -> None:
        pcr = [1.0, _PCR_PANIC_THRESHOLD, _PCR_PANIC_THRESHOLD - 0.05]
        status, vals = _check_signal3_pcr(pcr)
        assert status == SignalStatus.CONFIRMED
        assert vals["spike_detected_in_window"] is True


# ---------------------------------------------------------------------------
# Signal 4 — Breadth (I:S5O) dips below 30% then recovers
# ---------------------------------------------------------------------------


class TestSignal4Breadth:
    def test_confirmed_when_washout_occurred_and_recovered(self) -> None:
        # Values show dip below 30 then recovery above 30
        values = [50.0, 45.0, 28.0, 25.0, 35.0]
        status, vals = _check_signal4_breadth(values)
        assert status == SignalStatus.CONFIRMED
        assert vals["washout_occurred_in_window"] is True
        assert vals["currently_recovered"] is True

    def test_not_met_when_washout_not_yet_recovered(self) -> None:
        values = [50.0, 45.0, 28.0, 25.0, 22.0]
        status, vals = _check_signal4_breadth(values)
        assert status == SignalStatus.NOT_MET
        assert vals["currently_recovered"] is False

    def test_not_met_when_no_washout_occurred(self) -> None:
        values = [55.0, 50.0, 48.0, 52.0, 53.0]  # never below 30
        status, vals = _check_signal4_breadth(values)
        assert status == SignalStatus.NOT_MET
        assert vals["washout_occurred_in_window"] is False

    def test_unavailable_when_insufficient_data(self) -> None:
        status, vals = _check_signal4_breadth([25.0, 35.0])
        assert status == SignalStatus.UNAVAILABLE
        assert "reason" in vals

    def test_exactly_at_washout_threshold_qualifies(self) -> None:
        # <= threshold counts as washout
        values = [50.0, _BREADTH_WASHOUT_THRESHOLD, 35.0]
        status, vals = _check_signal4_breadth(values)
        assert status == SignalStatus.CONFIRMED
        assert vals["washout_occurred_in_window"] is True


# ---------------------------------------------------------------------------
# Crisis halt constant — hard stop replaces old Signal 5 geo flag
# ---------------------------------------------------------------------------


class TestCrisisHaltHardStop:
    """S5 geo flag removed — CRISIS HALT is now a hard stop checked in the gate
    before any signal evaluation. These tests verify the regime signal behaviour
    covers the hard stop path through _check_signal2_regime."""

    def test_signal2_not_met_on_crisis_halt(self) -> None:
        # When CRISIS HALT somehow reaches S2, it must not accidentally confirm.
        status, vals = _check_signal2_regime("CRISIS HALT")
        assert status == SignalStatus.NOT_MET

    def test_crisis_halt_label_constant_matches_regime_service(self) -> None:
        from atlas.services.regime_modifier_service import _rule_name  # type: ignore[attr-defined]
        assert _rule_name(1) == "CRISIS HALT"


# ---------------------------------------------------------------------------
# Gate determination
# ---------------------------------------------------------------------------


class TestDetermineGateStatus:
    def test_gate_passes_at_threshold(self) -> None:
        passed, gate_str, _ = _determine_gate_status(confirmed=3, unavailable=0)
        assert passed is True
        assert gate_str == "GREEN_LIGHT"

    def test_gate_passes_above_threshold(self) -> None:
        passed, gate_str, _ = _determine_gate_status(confirmed=5, unavailable=0)
        assert passed is True

    def test_gate_blocked_below_threshold(self) -> None:
        passed, gate_str, _ = _determine_gate_status(confirmed=2, unavailable=0)
        assert passed is False
        assert gate_str == "BLOCKED"

    def test_gate_blocked_with_unavailable_signals(self) -> None:
        # 2 confirmed + 2 unavailable → still blocked (need 3)
        passed, _, message = _determine_gate_status(confirmed=2, unavailable=2)
        assert passed is False
        assert "2" in message  # unavailable count in message

    def test_gate_message_mentions_confirmed_count(self) -> None:
        _, _, message = _determine_gate_status(confirmed=3, unavailable=1)
        assert "3" in message


# ---------------------------------------------------------------------------
# _compute_breadth_pct_series — pure function
# ---------------------------------------------------------------------------


class TestComputeBreadthPctSeries:
    """Tests for the pure % above 50-DMA breadth computation."""

    def _make_closes(self, sma_base: float, tail_value: float, history: int = 20) -> list[float]:
        """Build closes where SMA is sma_base and recent closes are tail_value."""
        return [sma_base] * 50 + [tail_value] * history

    def test_all_above_50dma_returns_100_pct(self) -> None:
        closes = self._make_closes(10.0, 12.0)
        result = _compute_breadth_pct_series(
            {"AAPL": closes, "MSFT": closes}, history_days=20, sma_window=50
        )
        assert len(result) == 20
        assert all(abs(pct - 100.0) < 0.01 for pct in result)

    def test_all_below_50dma_returns_0_pct(self) -> None:
        closes = self._make_closes(10.0, 8.0)
        result = _compute_breadth_pct_series(
            {"AAPL": closes, "MSFT": closes}, history_days=20, sma_window=50
        )
        assert len(result) == 20
        assert all(abs(pct) < 0.01 for pct in result)

    def test_half_above_returns_50_pct(self) -> None:
        above = self._make_closes(10.0, 12.0)
        below = self._make_closes(10.0, 8.0)
        result = _compute_breadth_pct_series(
            {"AAPL": above, "MSFT": below}, history_days=20, sma_window=50
        )
        assert len(result) == 20
        assert all(abs(pct - 50.0) < 0.01 for pct in result)

    def test_returns_empty_when_no_valid_tickers(self) -> None:
        # Only 30 bars — not enough for 50-DMA window
        closes = [10.0] * 30
        result = _compute_breadth_pct_series({"AAPL": closes}, history_days=20, sma_window=50)
        assert result == []

    def test_skips_ticker_with_insufficient_data(self) -> None:
        good = self._make_closes(10.0, 12.0)
        short = [10.0] * 30  # too short for 50-DMA
        result = _compute_breadth_pct_series(
            {"AAPL": good, "SHORT": short}, history_days=20, sma_window=50
        )
        assert len(result) == 20
        # Only AAPL counted → 100%
        assert all(abs(pct - 100.0) < 0.01 for pct in result)

    def test_series_length_matches_history_days(self) -> None:
        closes = [10.0] * 50 + [12.0] * 10
        result = _compute_breadth_pct_series({"AAPL": closes}, history_days=10, sma_window=50)
        assert len(result) == 10

    def test_empty_ticker_map_returns_empty_list(self) -> None:
        result = _compute_breadth_pct_series({}, history_days=20, sma_window=50)
        assert result == []

    def test_one_of_three_above_returns_33_pct(self) -> None:
        above = self._make_closes(10.0, 12.0)
        below = self._make_closes(10.0, 8.0)
        result = _compute_breadth_pct_series(
            {"A": above, "B": below, "C": below}, history_days=1, sma_window=50
        )
        assert len(result) == 1
        assert abs(result[0] - 33.33) < 0.01

    def test_values_rounded_to_2_decimal_places(self) -> None:
        above = self._make_closes(10.0, 12.0)
        below = self._make_closes(10.0, 8.0)
        result = _compute_breadth_pct_series(
            {"A": above, "B": below, "C": below}, history_days=1, sma_window=50
        )
        # Should be exactly 33.33, not 33.333333...
        assert result[0] == round(result[0], 2)


# ---------------------------------------------------------------------------
# _fetch_sp500_breadth_series — async, uses mock httpx client
# ---------------------------------------------------------------------------


class TestFetchSp500BreadthSeries:
    """Tests for the parallel Polygon fetch that computes S&P 500 breadth."""

    def _polygon_ok_response(self, closes: list[float]) -> MagicMock:
        bars = [{"c": c, "t": i * 86_400_000} for i, c in enumerate(closes)]
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"status": "OK", "results": bars}
        return mock

    def _polygon_empty_response(self) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"status": "OK", "results": []}
        return mock

    def _polygon_error_response(self, code: int = 403) -> MagicMock:
        mock = MagicMock()
        mock.status_code = code
        return mock

    async def test_returns_series_when_data_available(self) -> None:
        # 50 SMA bars + 30 above SMA → breadth ≈ 100%
        closes = [10.0] * 50 + [12.0] * 30
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._polygon_ok_response(closes))

        result = await _fetch_sp500_breadth_series("polygon-key", mock_client)

        assert result is not None
        assert len(result) >= 3
        assert all(pct > 90.0 for pct in result)

    async def test_returns_none_when_all_tickers_return_403(self) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._polygon_error_response(403))

        result = await _fetch_sp500_breadth_series("polygon-key", mock_client)

        assert result is None

    async def test_returns_none_when_all_results_empty(self) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._polygon_empty_response())

        result = await _fetch_sp500_breadth_series("polygon-key", mock_client)

        assert result is None

    async def test_returns_none_when_closes_too_short_for_sma(self) -> None:
        # Only 30 bars — below the 51-bar minimum for 50-DMA
        closes = [10.0] * 30
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._polygon_ok_response(closes))

        result = await _fetch_sp500_breadth_series("polygon-key", mock_client)

        assert result is None

    async def test_min_valid_tickers_constant_is_positive(self) -> None:
        assert _BREADTH_MIN_VALID_TICKERS > 0

