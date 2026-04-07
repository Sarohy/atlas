"""ORM model registry — import all models here so Alembic autogenerate picks them up."""

from atlas.models.position import Position

__all__ = ["Position"]
