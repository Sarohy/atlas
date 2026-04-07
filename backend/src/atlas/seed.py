"""Database seed helpers for local development."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.base import Base
from atlas.db.session import AsyncSessionLocal, engine
from atlas.models.user import User

INITIAL_ADMIN_EMAIL = "admin@atlas.com"
INITIAL_ADMIN_PASSWORD_HASH = (
    "pbkdf2_sha256$120000$4a1f9c7d3b2e1055c8a9f00177aa33cc$"
    "4db1a37f972741c476f472be72c347af73bbc8e424b8b33023c126a405e2e01f"
)


async def seed_initial_admin(session: AsyncSession) -> bool:
    """Create the initial admin user when it does not already exist."""
    result = await session.execute(select(User).where(User.email == INITIAL_ADMIN_EMAIL))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        return False

    user = User(
        email=INITIAL_ADMIN_EMAIL,
        password_hash=INITIAL_ADMIN_PASSWORD_HASH,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return True


async def seed_database() -> None:
    """Create tables and seed the initial admin user."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_initial_admin(session)


def main() -> None:
    """Run the seed workflow as a script entrypoint."""
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
