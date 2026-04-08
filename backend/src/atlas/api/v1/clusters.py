"""API routes for position clusters — CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.cluster import ClusterCreate, ClusterResponse, ClusterUpdate
from atlas.services.cluster_service import ClusterService

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterResponse])
async def list_clusters(
    session: AsyncSession = Depends(get_db_session),
) -> list[ClusterResponse]:
    """Return all clusters with their assigned tickers."""
    svc = ClusterService(session)
    return await svc.list_clusters()  # type: ignore[return-value]


@router.post("", response_model=ClusterResponse, status_code=201)
async def create_cluster(
    data: ClusterCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ClusterResponse:
    """Create a new cluster.

    Returns 409 if a cluster with the same name already exists.
    """
    svc = ClusterService(session)
    cluster = await svc.create_cluster(data)
    return cluster  # type: ignore[return-value]


@router.patch("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    data: ClusterUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ClusterResponse:
    """Update a cluster's name and/or colour."""
    svc = ClusterService(session)
    cluster = await svc.update_cluster(cluster_id, data)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found.")
    return cluster  # type: ignore[return-value]


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(
    cluster_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a cluster. Tickers that belonged to it become unassigned."""
    svc = ClusterService(session)
    deleted = await svc.delete_cluster(cluster_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found.")
