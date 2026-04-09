# ATLAS Backend

Decision-support API for active investing — FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · PostgreSQL · pip

---

## Prerequisites

| Tool       | Version | Install                                                                     |
| ---------- | ------- | --------------------------------------------------------------------------- |
| Python     | 3.12+   | [pyenv](https://github.com/pyenv/pyenv) or [python.org](https://python.org) |
| pip        | bundled | ships with Python 3.12+                                                     |
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

# Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements-dev.txt

# Copy and fill environment variables
cp .env.example .env
# Edit .env — set DATABASE_URL to your local postgres connection string

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push
```

---

## Running Tests

```bash
pytest
```

This runs all tests with coverage. The gate fails if coverage drops below **90%**.

To run a single file:

```bash
pytest tests/unit/test_health_schema.py -v
```

---

## Running the Dev Server

```bash
uvicorn atlas.main:create_app --factory --reload
```

The API is then available at `http://localhost:8000`.

Health check: `curl http://localhost:8000/api/v1/health`

Expected response:

```json
{ "status": "ok", "service": "atlas-backend" }
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1`  
All requests/responses are JSON. Full documentation with request bodies, response shapes, and error codes: [`src/atlas/api/v1/README.md`](src/atlas/api/v1/README.md)

### Quick reference

| Method   | Path                     | Description                                                         |
| -------- | ------------------------ | ------------------------------------------------------------------- |
| `GET`    | `/health`                | Service liveness — `{ "status": "ok", "service": "atlas-backend" }` |
| `POST`   | `/auth/sign-in`          | Authenticate — body: `{ email, password }`                          |
| `POST`   | `/auth/logout`           | Session cleanup (stateless)                                         |
| `GET`    | `/tickers`               | All portfolio tickers                                               |
| `POST`   | `/tickers`               | Add ticker — body: `{ ticker, shares, cluster_id? }`                |
| `PATCH`  | `/tickers/:id`           | Update shares / cluster — body: `{ shares?, cluster_id? }`          |
| `DELETE` | `/tickers/:id`           | Remove ticker                                                       |
| `POST`   | `/tickers/sync`          | Refresh market data from Polygon.io                                 |
| `GET`    | `/tickers/search?q=`     | Autocomplete ticker search via Polygon.io                           |
| `GET`    | `/portfolio/summary`     | NAV, cash breakdown, portfolio beta                                 |
| `GET`    | `/portfolio/cash`        | Current cash balance + floor %                                      |
| `PUT`    | `/portfolio/cash`        | Replace cash balance — body: `{ cash_balance, cash_floor_pct }`     |
| `POST`   | `/portfolio/cash/adjust` | Delta cash update — body: `{ amount }`                              |
| `GET`    | `/clusters`              | All clusters with assigned tickers                                  |
| `POST`   | `/clusters`              | Create cluster — body: `{ name, color }`                            |
| `PATCH`  | `/clusters/:id`          | Rename / recolour — body: `{ name?, color? }`                       |
| `DELETE` | `/clusters/:id`          | Delete cluster (tickers become unassigned)                          |
| `GET`    | `/watchlist`             | All watchlist items                                                 |
| `POST`   | `/watchlist`             | Add to watchlist — body: `{ ticker }`                               |
| `DELETE` | `/watchlist/:id`         | Remove from watchlist                                               |
| `POST`   | `/watchlist/sync`        | Refresh watchlist market data from Polygon.io                       |

### Interactive docs

When the dev server is running, FastAPI auto-generates interactive docs:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Quality Gate

Run before every commit:

```bash
ruff check .          # lint
ruff format --check . # formatting
mypy src              # type checks (strict mode)
pytest                # tests + coverage ≥ 90%
```

All four commands must exit 0.

---

## Database Migrations (Alembic)

```bash
# Apply all migrations to the dev database
alembic upgrade head

# Create a new migration after adding/changing a model
alembic revision --autogenerate -m "describe your change"
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
2. Run `pytest` — confirm the new test fails.
3. Write the **minimum** implementation to make it pass.
4. Run `pytest` — confirm all tests pass.
5. Refactor if needed. Tests still pass.
6. Run the full quality gate before committing.

Rules:

- Coverage must stay **≥ 90%** at all times.
- Every endpoint → integration test. Every schema → unit test. Every service → unit test with mocked deps.
- Test names are sentences: `test_health_endpoint_returns_ok_status`.
- All fixtures live in `conftest.py` — never copy-paste them.
