# db/ — Database Infrastructure

Session factory, declarative base, and Alembic migration setup.

## Files

| File            | Purpose                                                                    |
| --------------- | -------------------------------------------------------------------------- |
| `base.py`       | `DeclarativeBase` subclass — all models inherit from this                  |
| `session.py`    | Async engine + `async_sessionmaker`; `get_db_session()` FastAPI dependency |
| `migrations.py` | Any migration utilities (if present)                                       |

## Session usage

```python
from atlas.db.session import get_db_session

# In a FastAPI route:
async def my_route(session: AsyncSession = Depends(get_db_session)):
    ...
```

The engine reads `DATABASE_URL` from settings (`postgresql+asyncpg://...`).

## Migration workflow

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after changing a model
alembic revision --autogenerate -m "add conviction_score to tickers"

# Roll back one migration
alembic downgrade -1
```

Migrations live in `backend/alembic/versions/`. Every migration must be reversible — implement `downgrade()`.

## Layering rules

- `db/` is imported by `services/` only — never by `api/` directly.
- Always use async session: `await session.execute(...)`, `await session.commit()`.
- Never use `session.execute()` without `await` — sync calls will deadlock under asyncio.
