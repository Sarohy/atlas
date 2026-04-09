# ATLAS Backend — Hello World Setup Prompt

You are setting up the backend for **ATLAS**, a decision-support tool for active investing. This is the initial scaffold — a Hello World API — but it must follow production best practices and **strict test-driven development (TDD)** from commit one.

Do not skip steps. Do not write implementation code before tests. After each step, run the tests and confirm they pass before moving on.

---

## Project Context

ATLAS will eventually compute daily conviction scores for stock positions, enforce framework risk gates, and maintain an append-only Decision Trace log. None of that exists yet. Right now we are scaffolding the foundation with one working endpoint: `GET /health` returning `{"status": "ok", "service": "atlas-backend"}`.

The structure must support what is coming next: scoring jobs, market data ingestion, audit logging, and a strict API contract with the frontend.

---

## Tech Stack (non-negotiable)

- **Python 3.12+**
- **FastAPI** for the HTTP layer
- **Pydantic v2** for schemas and validation
- **SQLAlchemy 2.0** (async) + **Alembic** for ORM and migrations
- **PostgreSQL 16** as the database (installed locally — no Docker)
- **pytest** + **pytest-asyncio** + **httpx** for testing
- **pip** for dependency management (standard Python package manager)
- **ruff** for linting and formatting
- **mypy** in strict mode for type checking
- **pre-commit** hooks to enforce all of the above

---

## Required Project Structure

Create exactly this layout:

```
backend/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── README.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── atlas/
│       ├── __init__.py
│       ├── main.py             # FastAPI app factory
│       ├── config.py           # Pydantic Settings
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py         # shared FastAPI dependencies
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py   # aggregates v1 routers
│       │       └── health.py   # health endpoint
│       ├── core/
│       │   ├── __init__.py
│       │   └── logging.py      # structured logging setup
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py         # SQLAlchemy declarative base
│       │   └── session.py      # async engine + session factory
│       ├── models/             # SQLAlchemy models (empty for now)
│       │   └── __init__.py
│       ├── schemas/            # Pydantic schemas
│       │   ├── __init__.py
│       │   └── health.py
│       └── services/           # business logic (empty for now)
│           └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py             # shared fixtures
    ├── unit/
    │   ├── __init__.py
    │   └── test_health_schema.py
    └── integration/
        ├── __init__.py
        └── test_health_endpoint.py
```

---

## Step-by-Step Instructions

### Step 1 — Initialize the project

1. Create the `backend/` directory and `cd` into it.
2. Create and activate a virtual environment:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. Create the directory structure shown above. Every package directory needs an `__init__.py`.
5. Create `.gitignore` (Python defaults + `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`).

### Step 2 — Configure tooling

In `pyproject.toml` add these tool sections:

- `[tool.ruff]` — line length 100, target Python 3.12, enable rules `E,F,I,N,UP,B,A,C4,SIM,RUF`.
- `[tool.ruff.format]` — enable formatter.
- `[tool.mypy]` — strict mode, Python 3.12, disallow untyped defs, warn unused ignores.
- `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `asyncio_mode = "auto"`, `addopts = "-ra --strict-markers --cov=src/atlas --cov-report=term-missing --cov-fail-under=90"`.

Create `.pre-commit-config.yaml` with hooks for ruff (lint + format), mypy, and pytest (run on push only).

Run `pre-commit install` and `pre-commit install --hook-type pre-push`.

### Step 3 — Write the failing tests FIRST

This is the TDD step. Do not write any application code yet.

**`tests/conftest.py`** — create an async test client fixture using `httpx.AsyncClient` and `ASGITransport` pointing at the FastAPI app.

**`tests/unit/test_health_schema.py`** — write a test that:

- Imports `HealthResponse` from `atlas.schemas.health`
- Asserts it has fields `status: str` and `service: str`
- Asserts an instance with `status="ok"` and `service="atlas-backend"` serializes to the expected dict

**`tests/integration/test_health_endpoint.py`** — write a test that:

- Uses the async client fixture
- Calls `GET /api/v1/health`
- Asserts status code 200
- Asserts response JSON equals `{"status": "ok", "service": "atlas-backend"}`

Run `pytest`. **Confirm both tests fail** with import errors. This is correct — failing tests prove the test runner works.

### Step 4 — Implement the minimum code to pass

Now write only enough code to make the tests green:

1. **`src/atlas/config.py`** — Pydantic `Settings` class reading from environment with fields: `app_name: str = "atlas-backend"`, `environment: str = "development"`, `database_url: str`. Use `model_config = SettingsConfigDict(env_file=".env")`.
2. **`src/atlas/schemas/health.py`** — Pydantic `HealthResponse` model.
3. **`src/atlas/api/v1/health.py`** — FastAPI router with `GET /health` returning `HealthResponse`.
4. **`src/atlas/api/v1/router.py`** — `APIRouter` that includes the health router.
5. **`src/atlas/main.py`** — FastAPI app factory `create_app()` that mounts the v1 router under `/api/v1` and configures CORS for `http://localhost:3000`.
6. **`.env.example`** — document required env vars.

Run `pytest`. **Both tests must now pass.** Run `ruff check . && ruff format --check . && mypy src`. All must pass.

### Step 5 — Database scaffolding (no models yet)

**Prerequisite:** PostgreSQL 16 must be installed and running locally before this step.

- macOS: `brew install postgresql@16 && brew services start postgresql@16`
- Ubuntu/Debian: `sudo apt install postgresql-16 && sudo systemctl enable --now postgresql`
- Windows: install from https://www.postgresql.org/download/windows/ and start the service
- Verify: `psql --version` and `pg_isready` should both succeed.

1. **Create the local database and user:**
   ```bash
   createdb atlas_dev
   createdb atlas_test
   ```
   (If your local Postgres requires a superuser, prefix with `sudo -u postgres` on Linux.)
2. **Set `DATABASE_URL`** in `.env` to `postgresql+asyncpg://<your-user>@localhost:5432/atlas_dev` and document it in `.env.example`. The test database URL goes in the test fixtures.
3. **`src/atlas/db/base.py`** — SQLAlchemy `DeclarativeBase` subclass.
4. **`src/atlas/db/session.py`** — async engine and `async_sessionmaker` reading `database_url` from settings.
5. **`alembic.ini`** + **`alembic/env.py`** — configured for async, importing `Base` from `atlas.db.base`. No migrations yet.
6. Verify: `alembic revision --autogenerate -m "initial"` should produce an empty migration. Delete it — we don't commit empty migrations.

### Step 6 — Logging and final verification

1. **`src/atlas/core/logging.py`** — configure `structlog` for JSON output in production, pretty console output in development. Wire it into `create_app()`.
2. Add a startup log line confirming the app booted with environment name.
3. Run the full quality gate one more time:
   ```
   ruff check .
   ruff format --check .
   mypy src
   pytest --cov-fail-under=90
   ```
4. Start the server: `uvicorn atlas.main:create_app --factory --reload`
5. Manually verify `curl http://localhost:8000/api/v1/health` returns the expected JSON.

### Step 7 — Document and commit

1. Write a `README.md` covering: prerequisites, setup commands, how to run tests, how to run the dev server, project structure overview, and TDD workflow expectations.
2. Initialize git, make a single commit: `chore: initial backend scaffold with health endpoint`.

---

## TDD Rules You Must Follow Going Forward

These rules apply to **every future feature**, not just this scaffold:

1. **Red → Green → Refactor.** Write the failing test first. Write the minimum code to pass. Then refactor.
2. **No untested code paths.** Coverage must stay ≥90%. The pytest config enforces this.
3. **Every endpoint needs an integration test.** Every Pydantic schema needs a unit test. Every service function needs a unit test with mocked dependencies.
4. **Tests describe behavior, not implementation.** Test names read as sentences: `test_health_endpoint_returns_ok_status`.
5. **Fixtures live in `conftest.py`.** Never copy-paste fixture code across test files.
6. **Integration tests use a real test database** (separate from dev), spun up via a session-scoped fixture that runs migrations and tears down after.

---

## Acceptance Criteria

Before declaring this step done, confirm:

- [ ] `pytest` passes with ≥90% coverage
- [ ] `ruff check .` passes
- [ ] `mypy src` passes in strict mode
- [ ] `uvicorn atlas.main:create_app --factory` starts cleanly
- [ ] `curl http://localhost:8000/api/v1/health` returns `{"status":"ok","service":"atlas-backend"}`
- [ ] Local PostgreSQL is running and `atlas_dev` database exists
- [ ] `alembic upgrade head` runs without error
- [ ] Pre-commit hooks installed and passing
- [ ] README documents everything above

---

## What NOT to do

- Do not add scoring logic, market data clients, or auth yet — that's later phases.
- Do not skip the failing-test step. If you write code first, delete it and start over.
- Do not lower the coverage threshold.
- Do not commit with failing linters or type checks.
- Do not use sync SQLAlchemy. Async only.
- Do not put business logic in route handlers — they only call services.
