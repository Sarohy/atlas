"""F5 Fundamental Quality scoring service.

Computes five fundamental-quality indicators per the Factor_Mapping_Guide,
scores each 0-100, applies internal F5 weights, cap overrides, and produces
a 0-100 composite F5 score.

Data sources:
  sec-api.io            — Form 4 insider transactions (last 90 days)
  Alpha Vantage         — BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW, OVERVIEW

F5 internal weights (Factor_Mapping_Guide §F5):
  Insider Activity        30%  → max 30 pts contribution
  Altman Z-Score          25%  → max 25 pts contribution
  Free Cash Flow          20%  → max 20 pts contribution
  Debt / Equity           15%  → max 15 pts contribution
  Institutional Ownership 10%  → max 10 pts contribution
  TOTAL                  100%  → max 100 pts

Caps and hard blocks applied AFTER composite score is computed:
  C-suite officer sale >$1M  → F5 capped at 72
  CEO / CFO sale      >$10M  → F5 capped at 65
  Altman Z in 1.8–2.0        → F5 capped at 75
  Altman Z < 1.8             → Hard block  (f5_blocked = True)

All scoring helpers are pure functions (no I/O) so they can be unit-tested
independently.  FundamentalService owns all network I/O.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Final

import httpx

from atlas.schemas.fundamental import (
    AltmanZScoreIndicator,
    DebtEquityIndicator,
    F5Grade,
    FreeCashFlowIndicator,
    FundamentalResponse,
    InsiderActivityIndicator,
    InstitutionalOwnershipIndicator,
)

# ---------------------------------------------------------------------------
# F5 internal weights
# ---------------------------------------------------------------------------

_W_INSIDER: Final[float] = 0.30
_W_ALTMAN: Final[float] = 0.25
_W_FCF: Final[float] = 0.20
_W_DEBT: Final[float] = 0.15
_W_INST: Final[float] = 0.10

# ---------------------------------------------------------------------------
# Cap / block constants
# ---------------------------------------------------------------------------

_CAP_OFFICER_SELL: Final[int] = 72       # C-suite sale > $1M
_CAP_CEO_CFO_MEGA: Final[int] = 65       # CEO/CFO sale > $10M
_CAP_ALTMAN_GREY: Final[int] = 75        # Altman Z in grey zone 1.8–2.0
_OFFICER_SELL_THRESHOLD: Final[float] = 1_000_000.0
_CEO_CFO_MEGA_THRESHOLD: Final[float] = 10_000_000.0

# Altman Z zone thresholds
_Z_SAFE: Final[float] = 3.0
_Z_GOOD: Final[float] = 2.5
_Z_NEUTRAL: Final[float] = 2.0
_Z_GREY_LOW: Final[float] = 1.8

# Grade boundaries
_GRADE_STRONG: Final[int] = 80
_GRADE_GOOD: Final[int] = 65
_GRADE_NEUTRAL: Final[int] = 40
_GRADE_WEAK: Final[int] = 20

# API endpoints
_AV_BASE: Final[str] = "https://www.alphavantage.co/query"
_SEC_API_BASE: Final[str] = "https://api.sec-api.io"
_TIMEOUT: Final[float] = 15.0

# ---------------------------------------------------------------------------
# Pure scoring helpers — each returns 0-100
# ---------------------------------------------------------------------------


def _score_insider_activity(
    net_buy: float,
    net_sell: float,
    sell_transaction_count: int,
    ceo_cfo_sell: float,
) -> tuple[int, str]:
    """Score insider activity and derive the activity label.

    Returns (score, label) tuple.

    Guide:
      Net buying (buys > 0, no sells)    → 100  NET_BUYING
      No activity                        →  70  NO_ACTIVITY
      1 small sale (<$500K)              →  55  SMALL_SALE
      Multiple sales (≥2 transactions)   →  30  MULTIPLE_SALES
      CEO/CFO sale >$10M                 →  20  CEO_MEGA_SALE
    """
    if ceo_cfo_sell >= _CEO_CFO_MEGA_THRESHOLD:
        return 20, "CEO_MEGA_SALE"
    if net_buy > 0 and net_sell == 0:
        return 100, "NET_BUYING"
    if net_sell == 0 and net_buy == 0:
        return 70, "NO_ACTIVITY"
    if sell_transaction_count == 1 and net_sell < 500_000:
        return 55, "SMALL_SALE"
    return 30, "MULTIPLE_SALES"


def _score_altman_z(z: float | None) -> tuple[int, str]:
    """Map Altman Z-Score to a 0-100 raw score and zone label.

    Returns (score, zone) tuple.

    Guide:
      Z > 3.0      → 100   SAFE
      Z 2.5–3.0    →  85   SAFE
      Z 2.0–2.5    →  70   SAFE
      Z 1.8–2.0    →  55   GREY   (cap F5 at 75)
      Z < 1.8      →   0   DISTRESSED (hard block)
      Unknown      →  70   UNKNOWN
    """
    if z is None:
        return 70, "UNKNOWN"
    if z > _Z_SAFE:
        return 100, "SAFE"
    if z >= _Z_GOOD:
        return 85, "SAFE"
    if z >= _Z_NEUTRAL:
        return 70, "SAFE"
    if z >= _Z_GREY_LOW:
        return 55, "GREY"
    return 0, "DISTRESSED"


def _score_fcf(fcf_current: float | None, fcf_prior: float | None) -> tuple[int, str]:
    """Score Free Cash Flow level and trend.

    Returns (score, trend_label) tuple.

    Guide:
      Positive AND growing   → 100
      Positive AND flat      →  80
      Positive AND declining →  60
      Negative AND improving →  40
      Negative AND worsening →  20
      Unknown                →  60
    """
    if fcf_current is None:
        return 60, "UNKNOWN"

    positive = fcf_current > 0

    if fcf_prior is None:
        return (80 if positive else 40), ("POSITIVE_FLAT" if positive else "NEGATIVE_IMPROVING")

    # Threshold for "flat" — within 10% of prior
    if fcf_prior != 0:
        change_pct = (fcf_current - fcf_prior) / abs(fcf_prior)
    else:
        change_pct = 0.0

    growing = change_pct > 0.10
    declining = change_pct < -0.10

    if positive and growing:
        return 100, "POSITIVE_GROWING"
    if positive and not declining:
        return 80, "POSITIVE_FLAT"
    if positive and declining:
        return 60, "POSITIVE_DECLINING"
    # Negative FCF
    improving = fcf_current > fcf_prior  # less negative or turning positive
    if improving:
        return 40, "NEGATIVE_IMPROVING"
    return 20, "NEGATIVE_WORSENING"


def _score_debt_equity(ratio: float | None) -> int:
    """Map Debt/Equity ratio to a 0-100 raw score.

    Guide:
      D/E < 0.3   → 100
      D/E 0.3–0.6 →  85
      D/E 0.6–1.0 →  70
      D/E 1.0–2.0 →  50
      D/E > 2.0   →  25
      Unknown     →  65  (neutral)
    """
    if ratio is None:
        return 65
    if ratio < 0.3:
        return 100
    if ratio < 0.6:
        return 85
    if ratio < 1.0:
        return 70
    if ratio < 2.0:
        return 50
    return 25


def _score_institutional(ownership_pct: float | None) -> tuple[int, str]:
    """Map current institutional ownership % to a 0-100 score and change label.

    Returns (score, change_label).  Ownership_pct is a fraction (0.0–1.0).
    Using current % as a proxy for institutional conviction (per §F5, 13F
    historical change data not available in Alpha Vantage basic tier).

    Mapping:
      ≥ 0.70   → NET_BUYING    → 100
      0.50–0.70 → FLAT         →  80
      0.30–0.50 → FLAT         →  65
      0.10–0.30 → SMALL_SELLING →  45
      < 0.10   → LARGE_SELLING →  20
      Unknown  → FLAT           →  65
    """
    if ownership_pct is None:
        return 65, "FLAT"
    if ownership_pct >= 0.70:
        return 100, "NET_BUYING"
    if ownership_pct >= 0.50:
        return 80, "FLAT"
    if ownership_pct >= 0.30:
        return 65, "FLAT"
    if ownership_pct >= 0.10:
        return 45, "SMALL_SELLING"
    return 20, "LARGE_SELLING"


def _compute_altman_z(
    current_assets: float,
    current_liabilities: float,
    total_assets: float,
    retained_earnings: float,
    total_liabilities: float,
    ttm_ebit: float,
    ttm_revenue: float,
    market_cap: float,
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """Compute Altman Z-Score and its five component ratios.

    Returns (z_score, x1, x2, x3, x4, x5).
    Returns all-None when total_assets is zero or market data is unavailable.
    """
    if total_assets <= 0:
        return None, None, None, None, None, None

    x1 = (current_assets - current_liabilities) / total_assets
    x2 = retained_earnings / total_assets
    x3 = ttm_ebit / total_assets
    x4 = market_cap / total_liabilities if total_liabilities > 0 else 1.0
    x5 = ttm_revenue / total_assets

    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    return round(z, 4), round(x1, 4), round(x2, 4), round(x3, 4), round(x4, 4), round(x5, 4)


def _grade_from_score(score: int) -> str:
    if score >= _GRADE_STRONG:
        return F5Grade.STRONG
    if score >= _GRADE_GOOD:
        return F5Grade.GOOD
    if score >= _GRADE_NEUTRAL:
        return F5Grade.NEUTRAL
    if score >= _GRADE_WEAK:
        return F5Grade.WEAK
    return F5Grade.DISTRESSED


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        fv = float(value)
        return fv if fv != 0.0 else None
    except (TypeError, ValueError):
        return None


def _safe_float_zero(value: Any) -> float | None:
    """Like _safe_float but preserves 0.0 (used for FCF which can legitimately be zero)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class FundamentalService:
    """Fetches F5 data and computes the Fundamental Quality score.

    Requires two API keys:
      sec_api_key      — sec-api.io (Form 4 insider trades)
      alphavantage_key — Alpha Vantage (balance sheet, income, cash flow, overview)
    """

    def __init__(self, sec_api_key: str, alphavantage_key: str) -> None:
        self._sec_key = sec_api_key
        self._av_key = alphavantage_key

    async def compute_fundamental(self, ticker: str) -> FundamentalResponse:
        """Fetch all data sources and return a FundamentalResponse for ticker."""
        ticker = ticker.upper()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            insider_raw, bs_raw, inc_raw, cf_raw, ov_raw = await asyncio.gather(
                self._fetch_insider_trades(client, ticker),
                self._fetch_balance_sheet(client, ticker),
                self._fetch_income_statement(client, ticker),
                self._fetch_cash_flow(client, ticker),
                self._fetch_overview(client, ticker),
            )

        # ---- Insider Activity ------------------------------------------------
        insider_ind = self._build_insider_indicator(insider_raw)

        # ---- Balance sheet data extraction -----------------------------------
        bs = self._extract_balance_sheet(bs_raw)
        inc = self._extract_income_ttm(inc_raw)
        cf = self._extract_cash_flows(cf_raw)
        market_cap = self._extract_market_cap(ov_raw)

        # ---- Altman Z-Score --------------------------------------------------
        altman_ind = self._build_altman_indicator(bs, inc, market_cap)

        # ---- Free Cash Flow --------------------------------------------------
        fcf_ind = self._build_fcf_indicator(cf)

        # ---- Debt / Equity ---------------------------------------------------
        de_ind = self._build_debt_equity_indicator(bs)

        # ---- Institutional Ownership -----------------------------------------
        inst_ind = self._build_institutional_indicator(ov_raw)

        # ---- Weighted F5 composite -------------------------------------------
        f5_raw = (
            insider_ind.score * _W_INSIDER
            + altman_ind.score * _W_ALTMAN
            + fcf_ind.score * _W_FCF
            + de_ind.score * _W_DEBT
            + inst_ind.score * _W_INST
        )
        f5_score = round(f5_raw)

        # ---- Apply caps and hard block ---------------------------------------
        insider_cap: int | None = None
        altman_cap: int | None = None
        f5_blocked = False

        # Insider selling caps
        c_suite_sell = insider_ind.c_suite_sell_value or 0.0
        ceo_cfo_sell = insider_ind.ceo_cfo_sell_value or 0.0
        if ceo_cfo_sell >= _CEO_CFO_MEGA_THRESHOLD:
            insider_cap = _CAP_CEO_CFO_MEGA
        elif c_suite_sell >= _OFFICER_SELL_THRESHOLD:
            insider_cap = _CAP_OFFICER_SELL

        # Altman Z caps / block
        z = altman_ind.z_score
        if z is not None:
            if z < _Z_GREY_LOW:
                f5_blocked = True
            elif z < _Z_NEUTRAL:
                altman_cap = _CAP_ALTMAN_GREY

        # Determine active cap
        caps = [c for c in [insider_cap, altman_cap] if c is not None]
        active_cap = min(caps) if caps else None

        if active_cap is not None:
            f5_score = min(f5_score, active_cap)

        return FundamentalResponse(
            ticker=ticker,
            insider_activity=insider_ind,
            altman_z=altman_ind,
            free_cash_flow=fcf_ind,
            debt_equity=de_ind,
            institutional_ownership=inst_ind,
            insider_cap=insider_cap,
            altman_cap=altman_cap,
            f5_blocked=f5_blocked,
            active_cap=active_cap,
            f5_score=f5_score,
            f5_grade=_grade_from_score(f5_score),
        )

    # ------------------------------------------------------------------
    # SEC API — insider trading Form 4
    # ------------------------------------------------------------------

    async def _fetch_insider_trades(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]]:
        """Query sec-api.io for Form 4 filings in the last 90 days.

        Endpoint: POST https://api.sec-api.io/insider-trading
        """
        if not self._sec_key:
            return []

        cutoff = (date.today() - timedelta(days=90)).isoformat()
        query = f'issuer.tradingSymbol:{ticker} AND filedAt:[{cutoff} TO *]'

        try:
            resp = await client.post(
                f"{_SEC_API_BASE}/insider-trading",
                headers={"Authorization": self._sec_key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "from": 0,
                    "size": 50,
                    "sort": [{"filedAt": {"order": "desc"}}],
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            payload: Any = resp.json()
            # Response: {"transactions": [...], "total": N}
            if isinstance(payload, list):
                return payload
            return payload.get("transactions", payload.get("data", []))
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Alpha Vantage — balance sheet
    # ------------------------------------------------------------------

    async def _fetch_balance_sheet(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _AV_BASE,
                params={"function": "BALANCE_SHEET", "symbol": ticker, "apikey": self._av_key},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Alpha Vantage — income statement
    # ------------------------------------------------------------------

    async def _fetch_income_statement(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _AV_BASE,
                params={
                    "function": "INCOME_STATEMENT",
                    "symbol": ticker,
                    "apikey": self._av_key,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Alpha Vantage — cash flow
    # ------------------------------------------------------------------

    async def _fetch_cash_flow(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _AV_BASE,
                params={"function": "CASH_FLOW", "symbol": ticker, "apikey": self._av_key},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Alpha Vantage — overview (market cap, institutional ownership)
    # ------------------------------------------------------------------

    async def _fetch_overview(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _AV_BASE,
                params={"function": "OVERVIEW", "symbol": ticker, "apikey": self._av_key},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Indicator builders
    # ------------------------------------------------------------------

    def _build_insider_indicator(
        self, filings: list[dict[str, Any]]
    ) -> InsiderActivityIndicator:
        """Parse Form 4 filings and build the InsiderActivityIndicator."""
        net_buy: float = 0.0
        net_sell: float = 0.0
        sell_tx_count: int = 0
        c_suite_sell: float = 0.0
        ceo_cfo_sell: float = 0.0
        total_tx: int = 0

        for filing in filings:
            if not isinstance(filing, dict):
                continue

            owner = filing.get("reportingOwner", {})
            if isinstance(owner, list):
                owner = owner[0] if owner else {}

            relationship = owner.get("relationship", {})
            is_officer: bool = bool(relationship.get("isOfficer", False))
            officer_title: str = str(relationship.get("officerTitle", "")).lower()
            is_ceo_cfo = is_officer and any(
                kw in officer_title
                for kw in ("ceo", "cfo", "chief executive", "chief financial")
            )

            # Non-derivative transactions (open-market stock buys/sells)
            nd_table = filing.get("nonDerivativeTable", {})
            transactions: list[Any] = nd_table.get("transactions", []) if nd_table else []

            for tx in transactions:
                if not isinstance(tx, dict):
                    continue

                amounts = tx.get("amounts", {})
                code: str = (amounts.get("acquiredDisposedCode") or "").upper()

                try:
                    shares = float(amounts.get("shares") or 0)
                    price = float(amounts.get("pricePerShare") or 0)
                except (TypeError, ValueError):
                    continue

                # Only count open-market transactions (coding.code P or S)
                # acquiredDisposedCode: A = acquired, D = disposed
                tx_coding = tx.get("coding", {})
                market_code: str = (tx_coding.get("code") or "").upper()
                # Accept P (purchase) and S (sale) for open-market; skip grants/awards
                if market_code not in ("P", "S", ""):
                    continue

                value = shares * price
                total_tx += 1

                if code == "A":
                    net_buy += value
                elif code == "D":
                    net_sell += value
                    sell_tx_count += 1
                    if is_officer:
                        c_suite_sell += value
                    if is_ceo_cfo:
                        ceo_cfo_sell += value

        score, label = _score_insider_activity(net_buy, net_sell, sell_tx_count, ceo_cfo_sell)

        return InsiderActivityIndicator(
            net_buy_value=round(net_buy, 2) if net_buy > 0 else None,
            net_sell_value=round(net_sell, 2) if net_sell > 0 else None,
            transaction_count=total_tx,
            c_suite_sell_value=round(c_suite_sell, 2) if c_suite_sell > 0 else None,
            ceo_cfo_sell_value=round(ceo_cfo_sell, 2) if ceo_cfo_sell > 0 else None,
            activity_label=label,
            score=score,
            weight=_W_INSIDER,
        )

    def _build_altman_indicator(
        self,
        bs: dict[str, float | None],
        inc: dict[str, float | None],
        market_cap: float | None,
    ) -> AltmanZScoreIndicator:
        """Compute Altman Z-Score from parsed balance sheet and income data."""
        ta = bs.get("total_assets")
        ca = bs.get("current_assets")
        cl = bs.get("current_liabilities")
        re_ = bs.get("retained_earnings")
        tl = bs.get("total_liabilities")
        ttm_ebit = inc.get("ttm_operating_income")
        ttm_rev = inc.get("ttm_revenue")

        if None in (ta, ca, cl, re_, tl, ttm_ebit, ttm_rev, market_cap):
            return AltmanZScoreIndicator(
                score=70,
                weight=_W_ALTMAN,
                zone="UNKNOWN",
            )

        z, x1, x2, x3, x4, x5 = _compute_altman_z(
            current_assets=float(ca),  # type: ignore[arg-type]
            current_liabilities=float(cl),  # type: ignore[arg-type]
            total_assets=float(ta),  # type: ignore[arg-type]
            retained_earnings=float(re_),  # type: ignore[arg-type]
            total_liabilities=float(tl),  # type: ignore[arg-type]
            ttm_ebit=float(ttm_ebit),  # type: ignore[arg-type]
            ttm_revenue=float(ttm_rev),  # type: ignore[arg-type]
            market_cap=float(market_cap),  # type: ignore[arg-type]
        )

        score, zone = _score_altman_z(z)
        return AltmanZScoreIndicator(
            z_score=z,
            x1_working_capital_ratio=x1,
            x2_retained_earnings_ratio=x2,
            x3_ebit_ratio=x3,
            x4_market_cap_to_liabilities=x4,
            x5_revenue_to_assets=x5,
            zone=zone,
            score=score,
            weight=_W_ALTMAN,
        )

    def _build_fcf_indicator(self, cf: dict[str, float | None]) -> FreeCashFlowIndicator:
        fcf_cur = cf.get("fcf_current")
        fcf_pri = cf.get("fcf_prior")
        score, trend = _score_fcf(fcf_cur, fcf_pri)
        return FreeCashFlowIndicator(
            fcf_current=round(fcf_cur, 2) if fcf_cur is not None else None,
            fcf_prior=round(fcf_pri, 2) if fcf_pri is not None else None,
            fcf_trend=trend,
            score=score,
            weight=_W_FCF,
        )

    def _build_debt_equity_indicator(
        self, bs: dict[str, float | None]
    ) -> DebtEquityIndicator:
        debt = bs.get("total_debt")
        equity = bs.get("total_equity")

        ratio: float | None = None
        if debt is not None and equity is not None and equity != 0:
            ratio = round(debt / equity, 4)

        return DebtEquityIndicator(
            total_debt=round(debt, 2) if debt is not None else None,
            total_equity=round(equity, 2) if equity is not None else None,
            ratio=ratio,
            score=_score_debt_equity(ratio),
            weight=_W_DEBT,
        )

    def _build_institutional_indicator(
        self, overview: dict[str, Any]
    ) -> InstitutionalOwnershipIndicator:
        raw = overview.get("PercentInstitutionsOwnership") or overview.get(
            "percentInstitutionsOwnership"
        )
        pct: float | None = None
        if raw is not None:
            try:
                pct = float(raw)
                # AV returns as a decimal fraction (e.g. "0.623") OR a percentage
                # string ("62.3").  Normalise to fraction 0–1.
                if pct > 1.0:
                    pct = pct / 100.0
            except (TypeError, ValueError):
                pct = None

        score, label = _score_institutional(pct)
        return InstitutionalOwnershipIndicator(
            ownership_pct=round(pct, 4) if pct is not None else None,
            change_label=label,
            score=score,
            weight=_W_INST,
        )

    # ------------------------------------------------------------------
    # Raw data extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_balance_sheet(data: dict[str, Any]) -> dict[str, float | None]:
        """Extract most recent quarterly balance-sheet line items."""
        reports: list[dict[str, Any]] = data.get("quarterlyReports", [])
        if not reports:
            return {}

        rec = reports[0]  # most recent quarter

        def _f(key: str) -> float | None:
            return _safe_float(rec.get(key))

        total_assets = _f("totalAssets")
        current_assets = _f("totalCurrentAssets")
        current_liabilities = _f("totalCurrentLiabilities")
        retained = _f("retainedEarnings")
        equity = _f("totalShareholderEquity")

        # Total liabilities: prefer direct field, fall back to assets − equity
        total_liab = _f("totalLiabilities")
        if total_liab is None and total_assets is not None and equity is not None:
            total_liab = total_assets - equity

        # Total debt: prefer shortLongTermDebtTotal, then sum of parts
        total_debt = _f("shortLongTermDebtTotal")
        if total_debt is None:
            ltd = _f("longTermDebt") or 0.0
            std = _f("shortTermDebt") or _f("currentLongTermDebt") or 0.0
            sum_debt = ltd + std
            total_debt = sum_debt if sum_debt > 0 else None
        # If still None fall back to total liabilities (conservative)
        if total_debt is None:
            total_debt = total_liab

        return {
            "total_assets": total_assets,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "retained_earnings": retained,
            "total_liabilities": total_liab,
            "total_equity": equity,
            "total_debt": total_debt,
        }

    @staticmethod
    def _extract_income_ttm(data: dict[str, Any]) -> dict[str, float | None]:
        """Sum the 4 most recent quarterly income items for TTM totals."""
        reports: list[dict[str, Any]] = data.get("quarterlyReports", [])
        ttm_rev: float = 0.0
        ttm_op: float = 0.0
        count = 0

        for rec in reports[:4]:
            rev = _safe_float(rec.get("totalRevenue"))
            # Use ebit if available, else operatingIncome
            op = _safe_float(rec.get("ebit")) or _safe_float(rec.get("operatingIncome"))
            if rev is not None:
                ttm_rev += rev
                count += 1
            if op is not None:
                ttm_op += op

        return {
            "ttm_revenue": ttm_rev if count > 0 else None,
            "ttm_operating_income": ttm_op if count > 0 else None,
        }

    @staticmethod
    def _extract_cash_flows(data: dict[str, Any]) -> dict[str, float | None]:
        """Extract FCF for the two most recent quarters."""
        reports: list[dict[str, Any]] = data.get("quarterlyReports", [])

        def _fcf(rec: dict[str, Any]) -> float | None:
            op = _safe_float_zero(rec.get("operatingCashflow"))
            capex = _safe_float_zero(rec.get("capitalExpenditures"))
            if op is None:
                return None
            # Capital expenditures in AV may be reported as positive outflow;
            # FCF = operating - capex (treat as absolute deduction)
            capex_abs = abs(capex) if capex is not None else 0.0
            return op - capex_abs

        fcf_cur = _fcf(reports[0]) if len(reports) > 0 else None
        fcf_pri = _fcf(reports[1]) if len(reports) > 1 else None

        return {"fcf_current": fcf_cur, "fcf_prior": fcf_pri}

    @staticmethod
    def _extract_market_cap(overview: dict[str, Any]) -> float | None:
        raw = overview.get("MarketCapitalization") or overview.get("marketCapitalization")
        return _safe_float(raw)
