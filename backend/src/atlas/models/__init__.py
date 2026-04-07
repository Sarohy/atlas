"""ORM model registry — import all models here so Alembic autogenerate picks them up."""

from atlas.models.position import Position
from atlas.models.user import User

__all__ = ["Position", "User"]
