"""Unit tests for database base and session modules."""

from atlas.db.base import Base
from atlas.db.session import AsyncSessionLocal, engine, get_db_session


def test_base_is_declarative_base() -> None:
    """Base should be a valid SQLAlchemy DeclarativeBase subclass."""
    # DeclarativeBase subclasses have a metadata attribute
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


def test_engine_is_configured() -> None:
    """The async engine should be created with the correct dialect."""
    assert "postgresql" in str(engine.url)


def test_session_factory_is_configured() -> None:
    """AsyncSessionLocal should be an async_sessionmaker."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    assert isinstance(AsyncSessionLocal, async_sessionmaker)


async def test_get_db_session_yields_session() -> None:
    """get_db_session dependency yields an AsyncSession."""
    from sqlalchemy.ext.asyncio import AsyncSession

    gen = get_db_session()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    await session.close()
