"""FastAPI router for Framework 14 — Position Sizing Rules.

Endpoints:
  GET /api/v1/framework14/{ticker}
      Evaluate a single ticker position.
  GET /api/v1/framework14/cluster/{cluster_name}
      Evaluate a correlation cluster.

``position_weight_override`` and ``cluster_weight_override`` query params
allow test callers to bypass live DB queries (the same pattern used by
tranche_sizing and position_sizing routers).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.framework14 import ClusterSummaryResult, Framework14Result
from atlas.services.framework14_service import (
    CLUSTER_THRESHOLDS,
    TICKER_CLUSTER_MAP,
    evaluate_cluster,
    evaluate_framework14,
    get_cluster_weight,
)

router = APIRouter(prefix="/framework14", tags=["framework14"])

# Minimum ticker length accepted (reject whitespace-only strings)
_TICKER_MIN_LEN: int = 1


@router.get("/{ticker}", response_model=Framework14Result)
async def get_framework14(
    ticker: Annotated[
        str,
        Path(description="Ticker symbol (case-insensitive, e.g. 'MU')."),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    position_weight_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description=(
                "Override the live DB position weight (0.0-1.0 fraction). "
                "Intended for testing; omit in production."
            ),
        ),
    ] = None,
    cluster_weight_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description=(
                "Override the live DB cluster weight (0.0-1.0 fraction). "
                "Intended for testing; omit in production."
            ),
        ),
    ] = None,
) -> Framework14Result:
    """Return the full Framework 14 evaluation for a single ticker."""
    if not ticker.strip():
        raise HTTPException(status_code=422, detail="Ticker must not be blank.")
    return await evaluate_framework14(
        ticker=ticker,
        session=session,
        position_weight_override=position_weight_override,
        cluster_weight_override=cluster_weight_override,
    )


@router.get("/cluster/{cluster_name}", response_model=ClusterSummaryResult)
async def get_cluster_summary(
    cluster_name: Annotated[
        str,
        Path(description="Cluster name (e.g. 'AI Memory')."),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cluster_weight_override: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description="Override the live DB cluster weight for testing.",
        ),
    ] = None,
) -> ClusterSummaryResult:
    """Return the concentration status for a named correlation cluster."""
    if cluster_name not in CLUSTER_THRESHOLDS:
        raise HTTPException(
            status_code=404,
            detail=f"Cluster '{cluster_name}' is not recognised.",
        )

    if cluster_weight_override is not None:
        cluster_weight = cluster_weight_override
    else:
        cluster_weight = await get_cluster_weight(cluster_name, session)

    tickers_in_cluster = [t for t, c in TICKER_CLUSTER_MAP.items() if c == cluster_name]

    # Use any ticker from the cluster to drive evaluate_cluster
    representative = tickers_in_cluster[0] if tickers_in_cluster else ""
    clust = evaluate_cluster(representative, cluster_weight)
    thresholds = CLUSTER_THRESHOLDS[cluster_name]

    return ClusterSummaryResult(
        cluster=cluster_name,
        cluster_weight_pct=round(cluster_weight * 100, 4),
        cluster_status=clust["cluster_status"],  # type: ignore[arg-type]
        cluster_yellow_threshold=thresholds["yellow"],
        cluster_red_threshold=thresholds["red"],
        tickers=sorted(tickers_in_cluster),
        trim_recommended=bool(clust["trim_recommended"]),
    )
