"""Framework 8 — Insider Activity Flag service.

Queries sec-api.io Form 4 filings to detect recent significant officer selling
for a given ticker. Returns a simple boolean flag consumed by Framework 7.

Returns False (safe default — does not block adds) on:
  - Missing sec_api_key
  - Network or API errors
  - Malformed response

Returns True when a C-suite officer sale exceeding the threshold is detected
within the 30-day lookback window.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Final

import httpx

logger = logging.getLogger(__name__)

# Insider sale value (USD) above which the flag is raised.
_INSIDER_SALE_THRESHOLD: Final[float] = 500_000.0

# Calendar-day lookback window for insider transaction search.
_LOOKBACK_DAYS: Final[int] = 30

# sec-api.io endpoint for Form 4 insider-trading data.
_SEC_API_URL: Final[str] = "https://api.sec-api.io/insider-trading"


class Framework8Service:
    """Minimal Framework 8 — Insider Activity Flag.

    Checks sec-api.io for recent significant officer sales. Expands in a
    future iteration to score net insider direction over a longer window.

    Parameters
    ----------
    sec_api_key:
        API token for sec-api.io.  When empty, the service always returns
        False so Framework 7 operates without blocking all positions.
    """

    def __init__(self, sec_api_key: str) -> None:
        self._sec_api_key = sec_api_key

    async def get_insider_flag(self, ticker: str) -> bool:
        """Return True if significant insider selling detected in last 30 days.

        Safe default is False — a missing key or network failure must never
        cause Framework 7 to erroneously block position adds.
        """
        if not self._sec_api_key:
            return False

        cutoff = (date.today() - timedelta(days=_LOOKBACK_DAYS)).isoformat()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_SEC_API_URL}?token={self._sec_api_key}",
                    json={
                        "query": {
                            "query_string": {
                                "query": (
                                    f'issuerTradingSymbol:"{ticker.upper()}"'
                                    " AND transactionCode:S"
                                    " AND reportingOwnerRelationshipIsOfficer:true"
                                ),
                            },
                        },
                        "from": 0,
                        "size": 20,
                        "sort": [{"filedAt": {"order": "desc"}}],
                        "dateRange": {"startDate": cutoff},
                    },
                )

            if resp.status_code != 200:
                return False

            data: dict[str, Any] = resp.json()
            transactions: list[dict[str, Any]] = data.get("transactions", [])

            for tx in transactions:
                amounts: dict[str, Any] = tx.get("transactionAmounts", {}) or {}
                raw_value = amounts.get("transactionTotalValue", 0) or 0
                try:
                    if abs(float(raw_value)) > _INSIDER_SALE_THRESHOLD:
                        return True
                except (TypeError, ValueError):
                    continue

            return False

        except Exception as exc:
            logger.warning(
                "Framework 8 insider flag fetch failed; defaulting to False",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return False
