"""ORM model registry — import all models here so Alembic autogenerate picks them up."""

from atlas.models.cluster import Cluster
from atlas.models.leaps import LeapsIvHistory, LeapsPosition
from atlas.models.nav_history import NavHistory
from atlas.models.portfolio_config import PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.models.user import User
from atlas.models.watchlist import WatchlistItem

__all__ = [
    "Cluster",
    "LeapsIvHistory",
    "LeapsPosition",
    "NavHistory",
    "PortfolioConfig",
    "Ticker",
    "User",
    "WatchlistItem",
]
