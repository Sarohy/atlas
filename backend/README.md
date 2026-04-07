# ATLAS Backend

Decision-support API for active investing — FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · PostgreSQL · uv

---

## Prerequisites

| Tool       | Version | Install                                                                     |
| ---------- | ------- | --------------------------------------------------------------------------- |
| Python     | 3.12+   | [pyenv](https://github.com/pyenv/pyenv) or [python.org](https://python.org) |
| uv         | latest  | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                          |
| PostgreSQL | 14+     | `brew install postgresql@16` (macOS)                                        |

Ensure PostgreSQL is running and the following databases exist:

```bash
createdb atlas_dev
createdb atlas_test
```

---

## Setup

```bash
# Clone and enter the backend directory
cd backend

# Install all dependencies (creates .venv automatically)
uv sync

# Copy and fill environment variables
cp .env.example .env
# Edit .env — set DATABASE_URL to your local postgres connection string

# Install pre-commit hooks
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

---

## Running Tests

```bash
uv run pytest
```

This runs all tests with coverage. The gate fails if coverage drops below **90%**.

To run a single file:

```bash
uv run pytest tests/unit/test_health_schema.py -v
```

---

## Running the Dev Server

```bash
uv run uvicorn atlas.main:create_app --factory --reload
```

The API is then available at `http://localhost:8000`.

Health check: `curl http://localhost:8000/api/v1/health`

Expected response:

```json
{ "status": "ok", "service": "atlas-backend" }
```

---

## Quality Gate

Run before every commit:

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy src              # type checks (strict mode)
uv run pytest                # tests + coverage ≥ 90%
```

All four commands must exit 0.

---

## Database Migrations (Alembic)

```bash
# Apply all migrations to the dev database
uv run alembic upgrade head

# Create a new migration after adding/changing a model
uv run alembic revision --autogenerate -m "describe your change"
```

---

## Project Structure

```
backend/
├── src/atlas/
│   ├── main.py          # FastAPI app factory (create_app)
│   ├── config.py        # Pydantic Settings — reads from .env
│   ├── api/
│   │   ├── deps.py      # Shared FastAPI dependencies
│   │   └── v1/
│   │       ├── router.py   # Aggregated v1 router
│   │       └── health.py   # GET /health endpoint
│   ├── core/
│   │   └── logging.py   # structlog configuration
│   ├── db/
│   │   ├── base.py      # SQLAlchemy DeclarativeBase
│   │   └── session.py   # Async engine + session factory
│   ├── models/          # SQLAlchemy ORM models (future)
│   ├── schemas/
│   │   └── health.py    # Pydantic HealthResponse schema
│   └── services/        # Business logic (future)
├── tests/
│   ├── conftest.py      # Shared fixtures (async HTTP client)
│   ├── unit/            # Schema + service tests
│   └── integration/     # Endpoint tests (real ASGI transport)
├── alembic/             # Migration scripts
└── pyproject.toml       # All tool config (ruff, mypy, pytest)
```

---

## TDD Workflow

Every feature follows **Red → Green → Refactor**:

1. Write a failing test that describes the desired behaviour.
2. Run `uv run pytest` — confirm the new test fails.
3. Write the **minimum** implementation to make it pass.
4. Run `uv run pytest` — confirm all tests pass.
5. Refactor if needed. Tests still pass.
6. Run the full quality gate before committing.

Rules:

- Coverage must stay **≥ 90%** at all times.
- Every endpoint → integration test. Every schema → unit test. Every service → unit test with mocked deps.
- Test names are sentences: `test_health_endpoint_returns_ok_status`.
- All fixtures live in `conftest.py` — never copy-paste them.
