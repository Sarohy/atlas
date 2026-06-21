"""Flow Monitor — the final action gate for F4 (Flow Monitor Architecture §6).

The Flow Monitor is the ONLY layer allowed to emit a final add decision. F4b
(options-flow persistence) and F4a (equity / dark-pool accumulation) are inputs,
not actions: a supportive F4b never produces a BUY on its own. The Monitor
combines F4b + F4a + live tape with the order-time gates (price/VWAP, cluster,
SMH/breadth regime, position size) and resolves a single action.

This module is PURE (no I/O). The F4 service supplies F4b + F4a + live tape; the
order-time gates are optional inputs (None = "not evaluated here" — checked at
order time), so the Monitor never claims a full ADD it cannot stand behind.

Resolution mirrors the Flow Monitor Resolution Rules:
    F4b bullish + F4a bullish + improving  → ADD eligible only if order-time gates clear
    F4b bullish + F4a bullish + fading     → WATCH / wait for reset
    F4b bullish + F4a bearish              → CONFLICT / no chase
    F4b neutral + F4a bullish              → STARTER-watch (equity alone ≠ full add)
    F4b bearish + F4a bullish              → MIXED ABSORPTION / watch
    F4b bearish + F4a bearish              → AVOID / trim-watch
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class FlowMonitorAction:
    """Final action emitted by the Flow Monitor (the only add authority)."""

    ADD_ELIGIBLE: Final[str] = "ADD_ELIGIBLE"  # every evaluated gate cleared
    ADD_PENDING_GATES: Final[str] = "ADD_PENDING_GATES"  # F4 clear; order-time gates unchecked
    STARTER: Final[str] = "STARTER"  # small starter only; no full add
    WATCH: Final[str] = "WATCH"  # hold / no fresh add
    CONFLICT: Final[str] = "CONFLICT"  # options vs equity disagree; no chase
    MIXED_ABSORPTION: Final[str] = "MIXED_ABSORPTION"  # bearish options vs bullish equity
    TRIM_WATCH: Final[str] = "TRIM_WATCH"  # bearish both sides
    AVOID: Final[str] = "AVOID"  # distribution / aggressive bearish


# F4b band → directional class.
_F4B_SUPPORTIVE_MIN: Final[int] = 60  # Constructive (60) and up
_F4B_NEUTRAL_CONSTRUCTIVE_MIN: Final[int] = 55  # neutral-constructive (55-59)
_F4B_NEUTRAL_MIN: Final[int] = 50  # Neutral / neutral-constructive (50-59)
_F4B_AGGRESSIVE_BEAR_MAX: Final[int] = 34  # aggressive bearish

F4aState = Literal["BULLISH", "BEARISH", "FADING", "NEUTRAL"]

GateStatus = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True)
class Gate:
    name: str
    status: GateStatus
    detail: str


@dataclass(frozen=True)
class FlowMonitorInputs:
    f4b_score: int
    f4b_live_state: str = "Mixed / structured"
    f4a_state: F4aState = "NEUTRAL"
    # Order-time gates — None means "not evaluated here" (checked at order time).
    vwap_held: bool | None = None
    cluster_rolling: bool | None = None  # True = cluster rolling over (bad)
    smh_defensive: bool | None = None  # True = SMH Defensive Turn (bad)
    position_at_or_below_target: bool | None = None  # True = size gate allows add


@dataclass(frozen=True)
class FlowMonitorResult:
    action: str
    reason: str
    gates: list[Gate] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

_LIVE_IMPROVING: Final[frozenset[str]] = frozenset(
    {"Improving", "Bullish persistent", "Bullish reversal"}
)
_LIVE_FADING: Final[frozenset[str]] = frozenset(
    {"Deteriorating", "Bearish persistent", "Bearish reversal"}
)


def _f4b_class(score: int) -> str:
    if score >= _F4B_SUPPORTIVE_MIN:
        return "supportive"
    if score >= _F4B_NEUTRAL_MIN:
        return "neutral"
    return "bearish"


def _live_class(state: str) -> str:
    if state in _LIVE_IMPROVING:
        return "improving"
    if state in _LIVE_FADING:
        return "fading"
    return "flat"


# ---------------------------------------------------------------------------
# Order-time gate evaluation
# ---------------------------------------------------------------------------


def _order_time_gates(inp: FlowMonitorInputs) -> list[Gate]:
    """Evaluate the order-time gates; None inputs are UNKNOWN (not evaluated)."""

    def gate(name: str, ok: bool | None, pass_d: str, fail_d: str, unknown_d: str) -> Gate:
        if ok is None:
            return Gate(name, "UNKNOWN", unknown_d)
        return Gate(name, "PASS" if ok else "FAIL", pass_d if ok else fail_d)

    return [
        gate(
            "VWAP",
            inp.vwap_held,
            "price holding / reclaimed VWAP",
            "price below VWAP",
            "VWAP not evaluated (order-time gate)",
        ),
        gate(
            "Cluster",
            None if inp.cluster_rolling is None else not inp.cluster_rolling,
            "cluster firm / rotating in",
            "cluster rolling over",
            "cluster not evaluated (order-time gate)",
        ),
        gate(
            "SMH regime",
            None if inp.smh_defensive is None else not inp.smh_defensive,
            "SMH not in Defensive Turn",
            "SMH Defensive Turn — adds capped",
            "SMH regime not evaluated (order-time gate)",
        ),
        gate(
            "Position size",
            inp.position_at_or_below_target,
            "at/below target — size gate allows add",
            "over target — no add",
            "position size not evaluated (order-time gate)",
        ),
    ]


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def resolve_flow_monitor(inp: FlowMonitorInputs) -> FlowMonitorResult:
    """Combine F4b + F4a + live tape + order-time gates into one final action."""
    f4b = _f4b_class(inp.f4b_score)
    f4a = inp.f4a_state
    live = _live_class(inp.f4b_live_state)
    order_gates = _order_time_gates(inp)

    f4b_gate = Gate(
        "F4b options",
        "PASS" if f4b == "supportive" else ("UNKNOWN" if f4b == "neutral" else "FAIL"),
        f"F4b {inp.f4b_score} ({f4b}), live tape {inp.f4b_live_state.lower()}",
    )
    f4a_gate = Gate(
        "F4a equity",
        "PASS" if f4a == "BULLISH" else ("FAIL" if f4a in ("BEARISH", "FADING") else "UNKNOWN"),
        f"dark-pool {f4a.lower()}",
    )
    gates = [f4b_gate, f4a_gate, *order_gates]

    # --- Aggressive bearish options → avoid / hedge regardless --------------
    if inp.f4b_score <= _F4B_AGGRESSIVE_BEAR_MAX:
        return FlowMonitorResult(
            FlowMonitorAction.AVOID,
            "Aggressive bearish options — avoid / protect / hedge.",
            gates,
        )

    # --- Bearish options (35-49) --------------------------------------------
    if f4b == "bearish":
        if f4a == "BULLISH":
            return FlowMonitorResult(
                FlowMonitorAction.MIXED_ABSORPTION,
                "Mixed absorption — bearish options vs bullish equity accumulation; "
                "no full add (watch).",
                gates,
            )
        if f4a in ("BEARISH", "FADING"):
            return FlowMonitorResult(
                FlowMonitorAction.TRIM_WATCH,
                "Bearish options with distribution / sell-lean — avoid, trim-watch.",
                gates,
            )
        return FlowMonitorResult(
            FlowMonitorAction.WATCH,
            "Bearish options flow — add blocked; watch.",
            gates,
        )

    # --- Neutral options (50-59) --------------------------------------------
    if f4b == "neutral":
        if f4a == "BULLISH":
            return FlowMonitorResult(
                FlowMonitorAction.STARTER,
                "Neutral options with equity accumulation — starter-watch only; "
                "equity alone does not create a full add.",
                gates,
            )
        # Neutral-constructive (55-59): the options tape leans modestly bullish but
        # sits below the supportive (60+) threshold — a constructive-but-provisional
        # edge, not "no edge". Distinguish it from a genuinely balanced tape (50-54)
        # so the wording matches a positive bull share / hedged-bullish context.
        if inp.f4b_score >= _F4B_NEUTRAL_CONSTRUCTIVE_MIN:
            return FlowMonitorResult(
                FlowMonitorAction.WATCH,
                "Constructive but provisional options edge — no fresh add until "
                "extension / gates clear.",
                gates,
            )
        return FlowMonitorResult(
            FlowMonitorAction.WATCH,
            "No clear options edge — hold / no fresh add.",
            gates,
        )

    # --- Supportive options (60+) -------------------------------------------
    if f4a == "BEARISH":
        return FlowMonitorResult(
            FlowMonitorAction.CONFLICT,
            "Supportive options but equity distributing — conflict / no chase.",
            gates,
        )
    if f4a in ("NEUTRAL", "FADING"):
        return FlowMonitorResult(
            FlowMonitorAction.WATCH,
            "Options supportive but equity not confirming — no chase; watch.",
            gates,
        )
    if live == "fading":
        return FlowMonitorResult(
            FlowMonitorAction.WATCH,
            "Options supportive but live tape fading — wait for a reset; no fresh add.",
            gates,
        )

    # F4b + F4a aligned bullish and live not fading → the ADD path, gated by
    # the order-time gates.
    if any(g.status == "FAIL" for g in order_gates):
        failed = ", ".join(g.name for g in order_gates if g.status == "FAIL")
        return FlowMonitorResult(
            FlowMonitorAction.WATCH,
            f"F4b + F4a aligned, but order-time gate(s) failed: {failed} — no add.",
            gates,
        )
    if any(g.status == "UNKNOWN" for g in order_gates):
        pending = ", ".join(g.name for g in order_gates if g.status == "UNKNOWN")
        return FlowMonitorResult(
            FlowMonitorAction.ADD_PENDING_GATES,
            f"F4b + F4a aligned bullish — add eligible once order-time gates clear "
            f"({pending}).",
            gates,
        )
    return FlowMonitorResult(
        FlowMonitorAction.ADD_ELIGIBLE,
        "F4b + F4a aligned bullish and all gates clear — add eligible.",
        gates,
    )
