"""Unit tests for the Flow Monitor action gate (Flow Monitor Architecture §6)."""

from __future__ import annotations

from atlas.core.flow_monitor import (
    FlowMonitorAction,
    FlowMonitorInputs,
    resolve_flow_monitor,
)


def _r(**kw: object) -> str:
    return resolve_flow_monitor(FlowMonitorInputs(**kw)).action  # type: ignore[arg-type]


class TestResolutionTable:
    def test_bullish_options_bullish_equity_improving_no_external_gates(self) -> None:
        # F4b supportive + F4a bullish + improving, order-time gates not evaluated
        # → ADD pending gates (never a bare add).
        assert (
            _r(f4b_score=72, f4b_live_state="Improving", f4a_state="BULLISH")
            == FlowMonitorAction.ADD_PENDING_GATES
        )

    def test_bullish_bullish_improving_all_gates_clear_is_add_eligible(self) -> None:
        assert (
            _r(
                f4b_score=72,
                f4b_live_state="Improving",
                f4a_state="BULLISH",
                vwap_held=True,
                cluster_rolling=False,
                smh_defensive=False,
                position_at_or_below_target=True,
            )
            == FlowMonitorAction.ADD_ELIGIBLE
        )

    def test_bullish_bullish_but_a_gate_fails_is_watch(self) -> None:
        assert (
            _r(
                f4b_score=72,
                f4b_live_state="Improving",
                f4a_state="BULLISH",
                vwap_held=False,  # below VWAP
                cluster_rolling=False,
                smh_defensive=False,
                position_at_or_below_target=True,
            )
            == FlowMonitorAction.WATCH
        )

    def test_bullish_options_bullish_equity_fading_is_watch(self) -> None:
        assert (
            _r(f4b_score=72, f4b_live_state="Deteriorating", f4a_state="BULLISH")
            == FlowMonitorAction.WATCH
        )

    def test_bullish_options_bearish_equity_is_conflict(self) -> None:
        # Supportive options vs distributing equity → conflict / no chase (not avoid).
        assert (
            _r(f4b_score=72, f4b_live_state="Improving", f4a_state="BEARISH")
            == FlowMonitorAction.CONFLICT
        )

    def test_supportive_options_neutral_equity_is_watch(self) -> None:
        # Equity not confirming (neutral) → no chase, watch.
        assert (
            _r(f4b_score=72, f4b_live_state="Improving", f4a_state="NEUTRAL")
            == FlowMonitorAction.WATCH
        )

    def test_neutral_options_bullish_equity_is_starter(self) -> None:
        assert (
            _r(f4b_score=55, f4b_live_state="Improving", f4a_state="BULLISH")
            == FlowMonitorAction.STARTER
        )

    def test_bearish_options_bullish_equity_is_mixed_absorption(self) -> None:
        assert (
            _r(f4b_score=42, f4b_live_state="Mixed / structured", f4a_state="BULLISH")
            == FlowMonitorAction.MIXED_ABSORPTION
        )

    def test_bearish_options_bearish_equity_is_trim_watch(self) -> None:
        assert (
            _r(f4b_score=40, f4b_live_state="Deteriorating", f4a_state="BEARISH")
            == FlowMonitorAction.TRIM_WATCH
        )

    def test_aggressive_bearish_is_avoid(self) -> None:
        assert (
            _r(f4b_score=20, f4b_live_state="Deteriorating", f4a_state="NEUTRAL")
            == FlowMonitorAction.AVOID
        )


def test_flow_monitor_never_emits_buy_text() -> None:
    # The Monitor's reasons must never read as a bare BUY.
    for score in range(0, 101, 5):
        for f4a in ("BULLISH", "BEARISH", "FADING", "NEUTRAL"):
            res = resolve_flow_monitor(
                FlowMonitorInputs(f4b_score=score, f4a_state=f4a)  # type: ignore[arg-type]
            )
            assert "buy" not in res.reason.lower()


def test_gates_are_reported() -> None:
    res = resolve_flow_monitor(
        FlowMonitorInputs(f4b_score=72, f4b_live_state="Improving", f4a_state="BULLISH")
    )
    names = {g.name for g in res.gates}
    assert {"F4b options", "F4a equity", "VWAP", "Cluster", "SMH regime", "Position size"} <= names
    # Order-time gates are UNKNOWN when not supplied.
    vwap = next(g for g in res.gates if g.name == "VWAP")
    assert vwap.status == "UNKNOWN"
