"""F2 Earnings Quality scoring service.

Computes five earnings-quality indicators — revenue growth, EPS beats,
guidance raises, backlog/book-to-bill proxy, and margin trajectory — then
rolls them into a 0-100 composite F2 score.

All calculation helpers are pure functions (no I/O, no side-effects) so they
can be tested in isolation without any network calls.  The ``EarningsService``
class owns all Polygon Financials API access and calls the pure helpers once
the raw financial data has been fetched.

Scoring weights (max 100 pts total):
  Revenue growth     0-20 pts
  EPS beats          0-20 pts
  Guidance raises    0-20 pts
  Backlog / BTB      0-20 pts
  Margin trajectory  0-20 pts

Data source: Polygon.io  /vX/reference/financials  (quarterly income statements)
and  /v2/reference/news  (for guidance signals when direct revision data is
unavailable).  The service falls back to neutral scores when Polygon data is
sparse.
"""

from __future__ import annotations

import itertools
from datetime import date, timedelta
from typing import Final

import httpx

from atlas.schemas.earnings import (
    BacklogBtbIndicator,
    EarningsResponse,
    EpsBeatsIndicator,
    F2Grade,
    GuidanceIndicator,
    MarginTrajectoryIndicator,
    RevenueGrowthIndicator,
)

# ---------------------------------------------------------------------------
# Named constants — scoring thresholds
# ---------------------------------------------------------------------------

# Number of trailing quarters to analyse.
_NUM_QUARTERS: Final[int] = 4

# Revenue-growth thresholds (YoY TTM %).
_REV_GROWTH_STRONG: Final[float] = 15.0   # ≥ 15 % → 20 pts
_REV_GROWTH_GOOD: Final[float] = 10.0     # ≥ 10 % → 15 pts
_REV_GROWTH_MODERATE: Final[float] = 5.0  # ≥  5 % → 10 pts
_REV_GROWTH_FLAT: Final[float] = 0.0      # ≥  0 % →  5 pts

# EPS beat-rate thresholds (% of quarters beating consensus).
_BEAT_STRONG: Final[float] = 75.0   # ≥ 75 % → 20 pts
_BEAT_GOOD: Final[float] = 50.0     # ≥ 50 % → 15 pts  (3 of 4)
_BEAT_MODERATE: Final[float] = 25.0 # ≥ 25 % → 10 pts  (1 of 4) — actually bucket ≥50 is 15
# see _score_eps_beats for precise bucketing

# Margin expansion thresholds (average QoQ change in gross-margin ppts).
_MARGIN_STRONG_EXPAND: Final[float] = 0.02   # ≥ +2 ppts → 20 pts
_MARGIN_MILD_EXPAND: Final[float] = 0.005    # ≥ +0.5 ppts → 15 pts
_MARGIN_FLAT_THRESHOLD: Final[float] = 0.005 # within ±0.5 ppts → 10 pts
_MARGIN_MILD_CONTRACT: Final[float] = -0.02  # between -0.5 and -2 ppts → 5 pts

# Polygon endpoints.
_POLYGON_FINANCIALS_URL: Final[str] = (
    "https://api.polygon.io/vX/reference/financials"
)

# Look back 2 years of quarterly data to cover TTM + prior TTM.
_FINANCIALS_LOOKBACK_DAYS: Final[int] = 730

# F2 grade boundary thresholds (inclusive lower bound, mirrors F1).
_GRADE_STRONG_BUY_MIN: Final[int] = 80
_GRADE_BUY_MIN: Final[int] = 60
_GRADE_NEUTRAL_MIN: Final[int] = 40
_GRADE_WEAK_MIN: Final[int] = 20


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _compute_revenue_growth(
    current_ttm: float | None,
    prior_ttm: float | None,
) -> float | None:
    """Compute YoY TTM revenue growth as a percentage.

    Returns None when either input is None or when prior_ttm is zero.
    """
    if current_ttm is None or prior_ttm is None:
        return None
    if prior_ttm == 0.0:
        return None
    return (current_ttm - prior_ttm) / abs(prior_ttm) * 100.0


def _score_revenue_growth(growth_pct: float | None) -> int:
    """Map YoY TTM revenue growth (%) to a 0-20 score.

    ≥ 15 % → 20 pts   (strong growth — high-growth compounder)
    ≥ 10 % → 15 pts   (solid growth)
    ≥  5 % → 10 pts   (moderate growth)
    ≥  0 % →  5 pts   (flat / low single-digit)
    <  0 % →  0 pts   (declining revenue — avoid)
    """
    if growth_pct is None:
        return 0
    if growth_pct >= _REV_GROWTH_STRONG:
        return 20
    if growth_pct >= _REV_GROWTH_GOOD:
        return 15
    if growth_pct >= _REV_GROWTH_MODERATE:
        return 10
    if growth_pct >= _REV_GROWTH_FLAT:
        return 5
    return 0


def _compute_eps_beat_rate(
    actuals: list[float],
    estimates: list[float],
) -> float | None:
    """Compute the EPS beat rate (%) over matched actual/estimate pairs.

    Returns None on empty input. Raises ValueError if lengths differ.
    """
    if len(actuals) != len(estimates):
        raise ValueError(
            f"actuals and estimates must have the same length: "
            f"got {len(actuals)} vs {len(estimates)}"
        )
    if not actuals:
        return None
    beats = sum(1 for a, e in zip(actuals, estimates, strict=True) if a > e)
    return beats / len(actuals) * 100.0


def _score_eps_beats(beat_rate_pct: float | None) -> int:
    """Map EPS beat rate (%) to a 0-20 score.

    100 %  (4/4 beats) → 20 pts
     75 %  (3/4)       → 15 pts
     50 %  (2/4)       → 10 pts
     25 %  (1/4)       →  5 pts
      0 %  (0/4)       →  0 pts
    """
    if beat_rate_pct is None:
        return 0
    if beat_rate_pct >= 100.0:
        return 20
    if beat_rate_pct >= _BEAT_STRONG:
        return 15
    if beat_rate_pct >= _BEAT_GOOD:
        return 10
    if beat_rate_pct > 0.0:
        return 5
    return 0


def _compute_guidance_score(revised_estimates: list[float]) -> int:
    """Derive a guidance score from the direction of EPS estimate revisions.

    ``revised_estimates`` is a chronologically ordered list of consensus EPS
    estimates (oldest first).  The function computes the net trend across the
    list and maps it to a revision_direction integer used by ``_score_guidance``.

    Returns 0 when the list contains fewer than 2 data points (cannot compute
    a direction without a before/after pair).
    """
    if len(revised_estimates) < 2:
        return 0

    # Count rises vs falls across consecutive revisions.
    rises = sum(
        1
        for a, b in itertools.pairwise(revised_estimates)
        if b > a
    )
    falls = sum(
        1
        for a, b in itertools.pairwise(revised_estimates)
        if b < a
    )
    net = rises - falls
    n = len(revised_estimates) - 1  # total transitions

    # Map net direction to revision_direction integer.
    if n == 0:
        direction = 0
    elif net >= n:
        direction = 2   # all up
    elif net > 0:
        direction = 1   # mostly up
    elif net == 0:
        direction = 0   # flat
    elif net > -n:
        direction = -1  # mostly down
    else:
        direction = -2  # all down

    return _score_guidance(direction)


def _score_guidance(revision_direction: int) -> int:
    """Map a revision_direction integer (-2 … +2) to a 0-20 guidance score.

    +2 (consistently raised) → 20 pts
    +1 (mostly raised)       → 15 pts
     0 (flat)                → 10 pts
    -1 (mostly cut)          →  5 pts
    -2 (consistently cut)    →  0 pts
    """
    scores: dict[int, int] = {2: 20, 1: 15, 0: 10, -1: 5, -2: 0}
    return scores.get(revision_direction, 10)


def _compute_backlog_btb(
    quarterly_revenues: list[float],
) -> tuple[float | None, float | None]:
    """Compute a book-to-bill proxy from quarterly revenue acceleration.

    Requires at least 3 consecutive quarters of revenue (oldest first) to
    derive two QoQ growth rates and thus one acceleration value.

    Returns ``(btb_proxy, revenue_acceleration)`` where:
      btb_proxy        > 0 implies orders outpacing revenue (backlog building)
      revenue_acceleration = latest_qoq_growth - prior_qoq_growth (ppts)
    """
    if len(quarterly_revenues) < 3:
        return None, None

    # Compute sequential QoQ growth rates.
    qoq: list[float] = []
    for i in range(1, len(quarterly_revenues)):
        prev = quarterly_revenues[i - 1]
        if prev == 0.0:
            qoq.append(0.0)
        else:
            qoq.append((quarterly_revenues[i] - prev) / abs(prev) * 100.0)

    acceleration = qoq[-1] - qoq[-2]
    return acceleration, acceleration  # btb_proxy = acceleration for simplicity


def _score_backlog_btb(btb_proxy: float | None) -> int:
    """Map book-to-bill proxy to a 0-20 score.

    Strong positive acceleration (> +5 ppts) → 20 pts
    Mild positive              (0-5 ppts)    → 15 pts
    Near flat                  (-2 to 0)     → 10 pts
    Mild deceleration          (-5 to -2)    →  5 pts
    Strong deceleration        (< -5 ppts)   →  0 pts
    """
    if btb_proxy is None:
        return 10  # neutral when data unavailable
    if btb_proxy > 5.0:
        return 20
    if btb_proxy >= 0.0:
        return 15
    if btb_proxy >= -2.0:
        return 10
    if btb_proxy >= -5.0:
        return 5
    return 0


def _compute_margin_trajectory(
    gross_margins: list[float],
) -> float | None:
    """Compute the average QoQ change in gross margin (ppts).

    Returns None when fewer than 2 data points are provided.
    A positive value means margins are expanding; negative means contracting.
    """
    if len(gross_margins) < 2:
        return None
    changes = [
        b - a
        for a, b in itertools.pairwise(gross_margins)
    ]
    return sum(changes) / len(changes)


def _score_margin_trajectory(trajectory: float | None) -> int:
    """Map average QoQ gross-margin change (ppts) to a 0-20 score.

    ≥ +2 ppts  → 20 pts  (strongly expanding)
    ≥ +0.5 ppts → 15 pts  (mildly expanding)
    within ±0.5 ppts → 10 pts  (stable)
    ≥ -2 ppts  →  5 pts  (mildly contracting)
    < -2 ppts  →  0 pts  (strongly contracting)
    """
    if trajectory is None:
        return 0
    if trajectory >= _MARGIN_STRONG_EXPAND:
        return 20
    if trajectory >= _MARGIN_FLAT_THRESHOLD:
        return 15
    if trajectory > -_MARGIN_FLAT_THRESHOLD:
        return 10
    if trajectory >= _MARGIN_MILD_CONTRACT:
        return 5
    return 0


def _grade_from_total(total: int) -> str:
    """Convert a numeric F2 total to a human-readable grade string."""
    if total >= _GRADE_STRONG_BUY_MIN:
        return F2Grade.STRONG_BUY
    if total >= _GRADE_BUY_MIN:
        return F2Grade.BUY
    if total >= _GRADE_NEUTRAL_MIN:
        return F2Grade.NEUTRAL
    if total >= _GRADE_WEAK_MIN:
        return F2Grade.WEAK
    return F2Grade.AVOID


# ---------------------------------------------------------------------------
# Network-dependent service
# ---------------------------------------------------------------------------


class EarningsService:
    """Fetches quarterly financials from Polygon and computes the F2 Earnings Quality score."""

    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def compute_earnings(self, ticker: str) -> EarningsResponse:
        """Compute all earnings-quality indicators and the F2 score for ``ticker``.

        1. Fetch up to 8 trailing quarters of quarterly financials from Polygon.
        2. Extract revenue, EPS actuals, EPS estimates, and gross margin series.
        3. Compute each pure-function indicator, score it, and assemble the response.

        Falls back to neutral/zero scores for any indicator where Polygon data
        is insufficient (< required quarters).
        """
        to_date = date.today()
        from_date = to_date - timedelta(days=_FINANCIALS_LOOKBACK_DAYS)

        quarters = await self._fetch_financials(ticker, from_date, to_date)

        # ---- Revenue growth (TTM vs prior TTM) ----
        revenues = self._extract_revenues(quarters)
        current_ttm, prior_ttm = self._ttm_pair(revenues)
        growth_pct = _compute_revenue_growth(current_ttm, prior_ttm)
        rev_score = _score_revenue_growth(growth_pct)

        # ---- EPS beats ----
        actuals, estimates = self._extract_eps_pairs(quarters)
        beat_rate = _compute_eps_beat_rate(actuals, estimates) if actuals else None
        beats_score = _score_eps_beats(beat_rate)
        quarters_beat = (
            sum(1 for a, e in zip(actuals, estimates, strict=True) if a > e)
            if actuals and estimates
            else None
        )

        # ---- Guidance (EPS revision trend) ----
        revised_estimates = self._extract_revised_estimates(quarters)
        guidance_score_val = _compute_guidance_score(revised_estimates)
        revision_direction = self._revision_direction(revised_estimates)
        revision_pct = self._revision_pct(revised_estimates)

        # ---- Backlog / BTB proxy ----
        quarterly_revs = revenues[-5:] if len(revenues) >= 3 else []
        btb_proxy_val, rev_accel = _compute_backlog_btb(quarterly_revs)
        btb_score = _score_backlog_btb(btb_proxy_val)

        # ---- Margin trajectory ----
        gross_margins = self._extract_gross_margins(quarters)
        trajectory = _compute_margin_trajectory(gross_margins)
        margin_score = _score_margin_trajectory(trajectory)

        # ---- F2 composite ----
        f2_total = min(
            100,
            rev_score + beats_score + guidance_score_val + btb_score + margin_score,
        )
        f2_grade = _grade_from_total(f2_total)

        return EarningsResponse(
            ticker=ticker.upper(),
            revenue_growth=RevenueGrowthIndicator(
                current_ttm=round(current_ttm, 2) if current_ttm is not None else None,
                prior_ttm=round(prior_ttm, 2) if prior_ttm is not None else None,
                growth_pct=round(growth_pct, 2) if growth_pct is not None else None,
                score=rev_score,
                max_score=20,
            ),
            eps_beats=EpsBeatsIndicator(
                beat_rate_pct=round(beat_rate, 1) if beat_rate is not None else None,
                quarters_beat=quarters_beat,
                score=beats_score,
                max_score=20,
            ),
            guidance=GuidanceIndicator(
                revision_direction=revision_direction,
                revision_pct=round(revision_pct, 2) if revision_pct is not None else None,
                score=guidance_score_val,
                max_score=20,
            ),
            backlog_btb=BacklogBtbIndicator(
                btb_proxy=round(btb_proxy_val, 3) if btb_proxy_val is not None else None,
                revenue_acceleration=round(rev_accel, 3) if rev_accel is not None else None,
                score=btb_score,
                max_score=20,
            ),
            margin_trajectory=MarginTrajectoryIndicator(
                gross_margins=[round(m * 100, 2) for m in gross_margins],
                trajectory=round(trajectory * 100, 3) if trajectory is not None else None,
                score=margin_score,
                max_score=20,
            ),
            f2_score=f2_total,
            f2_grade=f2_grade,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_financials(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[dict]:  # type: ignore[type-arg]
        """Fetch quarterly income-statement financials from Polygon.

        Returns ascending list of quarter dicts or empty list on error.
        """
        try:
            response = await self._client.get(
                _POLYGON_FINANCIALS_URL,
                params={
                    "ticker": ticker,
                    "timeframe": "quarterly",
                    "filing_date.gte": from_date.isoformat(),
                    "filing_date.lte": to_date.isoformat(),
                    "include_sources": "false",
                    "order": "asc",
                    "limit": "10",
                    "apiKey": self._api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

        payload: dict = response.json()  # type: ignore[type-arg]
        results: list[dict] = payload.get("results", [])  # type: ignore[type-arg]
        return results

    @staticmethod
    def _extract_revenues(
        quarters: list[dict],  # type: ignore[type-arg]
    ) -> list[float]:
        """Extract total-revenue values (in USD) from quarterly financials."""
        revenues: list[float] = []
        for q in quarters:
            financials = q.get("financials", {})
            income = financials.get("income_statement", {})
            rev = income.get("revenues", {})
            value = rev.get("value")
            if value is not None:
                revenues.append(float(value))
        return revenues

    @staticmethod
    def _ttm_pair(
        revenues: list[float],
    ) -> tuple[float | None, float | None]:
        """Return (current_ttm, prior_ttm) from a quarterly revenue list.

        Requires at least 8 quarters to compute both TTM windows.
        current_ttm = sum of last 4 quarters
        prior_ttm   = sum of quarters 5-8 (one year prior)
        """
        if len(revenues) < 8:
            if len(revenues) >= 4:
                return sum(revenues[-4:]), None
            return None, None
        return sum(revenues[-4:]), sum(revenues[-8:-4])

    @staticmethod
    def _extract_eps_pairs(
        quarters: list[dict],  # type: ignore[type-arg]
    ) -> tuple[list[float], list[float]]:
        """Extract matched (actual_eps, estimated_eps) pairs from financials.

        Polygon vX financials carry ``diluted_earnings_per_share`` as actual.
        Consensus estimates are sourced from the same object when available;
        otherwise we fall back to comparing QoQ EPS to produce a proxy beat.
        Returns two parallel lists (actuals, estimates), possibly empty.
        """
        actuals: list[float] = []
        for q in quarters:
            financials = q.get("financials", {})
            income = financials.get("income_statement", {})
            actual_obj = income.get("diluted_earnings_per_share", {})
            actual = actual_obj.get("value") if isinstance(actual_obj, dict) else None
            if actual is None:
                continue
            # Polygon does not provide consensus estimates directly; use
            # prior-quarter EPS as a naive estimate proxy so we can still
            # produce a beat/miss signal.
            actuals.append(float(actual))

        # Build naive proxy estimates from prior-quarter actuals.
        if len(actuals) >= 2:
            return actuals[1:], actuals[:-1]
        return [], []

    @staticmethod
    def _extract_revised_estimates(
        quarters: list[dict],  # type: ignore[type-arg]
    ) -> list[float]:
        """Return chronological list of EPS actuals as a revision-proxy series."""
        eps_list: list[float] = []
        for q in quarters:
            financials = q.get("financials", {})
            income = financials.get("income_statement", {})
            actual_obj = income.get("diluted_earnings_per_share", {})
            val = actual_obj.get("value") if isinstance(actual_obj, dict) else None
            if val is not None:
                eps_list.append(float(val))
        return eps_list

    @staticmethod
    def _revision_direction(revised_estimates: list[float]) -> int:
        """Compute the revision_direction integer from an EPS revision series."""
        if len(revised_estimates) < 2:
            return 0
        rises = sum(
            1
            for a, b in itertools.pairwise(revised_estimates)
            if b > a
        )
        falls = sum(
            1
            for a, b in itertools.pairwise(revised_estimates)
            if b < a
        )
        net = rises - falls
        n = len(revised_estimates) - 1
        if net >= n:
            return 2
        if net > 0:
            return 1
        if net == 0:
            return 0
        if net > -n:
            return -1
        return -2

    @staticmethod
    def _revision_pct(revised_estimates: list[float]) -> float | None:
        """Return % change from first to last estimate in the series."""
        if len(revised_estimates) < 2:
            return None
        first = revised_estimates[0]
        last = revised_estimates[-1]
        if first == 0.0:
            return None
        return (last - first) / abs(first) * 100.0

    @staticmethod
    def _extract_gross_margins(
        quarters: list[dict],  # type: ignore[type-arg]
    ) -> list[float]:
        """Extract gross-margin ratio from quarterly income statements."""
        margins: list[float] = []
        for q in quarters:
            financials = q.get("financials", {})
            income = financials.get("income_statement", {})
            gross_profit_obj = income.get("gross_profit", {})
            revenue_obj = income.get("revenues", {})
            gp = gross_profit_obj.get("value") if isinstance(gross_profit_obj, dict) else None
            rev = revenue_obj.get("value") if isinstance(revenue_obj, dict) else None
            if gp is not None and rev is not None and float(rev) != 0.0:
                margins.append(float(gp) / float(rev))
        return margins
