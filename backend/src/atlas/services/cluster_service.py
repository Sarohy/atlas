"""Business logic for managing position clusters."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from atlas.models.cluster import Cluster
from atlas.schemas.cluster import ClusterCreate, ClusterUpdate


class ClusterService:
    """All database interactions for the clusters feature."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_clusters(self) -> list[Cluster]:
        """Return all clusters ordered by name, with their tickers eagerly loaded."""
        result = await self._session.execute(
            select(Cluster)
            .options(selectinload(Cluster.tickers))
            .order_by(Cluster.name)
        )
        return list(result.scalars().all())

    async def get_cluster(self, cluster_id: int) -> Cluster | None:
        """Fetch a single cluster with tickers. Returns None if not found."""
        result = await self._session.execute(
            select(Cluster)
            .options(selectinload(Cluster.tickers))
            .where(Cluster.id == cluster_id)
        )
        return result.scalar_one_or_none()

    async def create_cluster(self, data: ClusterCreate) -> Cluster:
        """Insert a new cluster and return the persisted record."""
        cluster = Cluster(name=data.name, color=data.color)
        self._session.add(cluster)
        await self._session.flush()
        # Re-fetch with selectinload so the response includes the (empty) tickers list.
        result = await self._session.execute(
            select(Cluster)
            .options(selectinload(Cluster.tickers))
            .where(Cluster.id == cluster.id)
        )
        return result.scalar_one()

    async def update_cluster(self, cluster_id: int, data: ClusterUpdate) -> Cluster | None:
        """Update a cluster's name and/or colour. Returns None if not found."""
        cluster = await self._session.get(Cluster, cluster_id)
        if cluster is None:
            return None
        if data.name is not None:
            cluster.name = data.name
        if data.color is not None:
            cluster.color = data.color
        await self._session.flush()
        # Re-fetch with tickers after the update.
        result = await self._session.execute(
            select(Cluster)
            .options(selectinload(Cluster.tickers))
            .where(Cluster.id == cluster_id)
        )
        return result.scalar_one_or_none()

    async def delete_cluster(self, cluster_id: int) -> bool:
        """Delete a cluster by id. Tickers lose their cluster assignment (SET NULL).

        Returns True on success, False if not found.
        """
        cluster = await self._session.get(Cluster, cluster_id)
        if cluster is None:
            return False
        await self._session.delete(cluster)
        await self._session.flush()
        return True
