# tests/ — Test Suite

pytest + pytest-asyncio. Coverage gate: **≥ 90%** (enforced by `pyproject.toml`).

## Structure

```
tests/
├── conftest.py          — shared fixtures (async HTTP client, test DB session)
├── unit/
│   ├── models/          — ORM model tests
│   ├── schemas/         — Pydantic schema validation tests
│   ├── services/        — service unit tests (mocked DB/HTTP dependencies)
│   ├── test_auth_service.py
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_health_schema.py
│   ├── test_logging.py
│   ├── test_security.py
│   └── test_seed.py
└── integration/
    ├── test_auth_endpoint.py
    ├── test_clusters_endpoint.py
    ├── test_cors.py
    ├── test_health_endpoint.py
    ├── test_portfolio_endpoint.py
    ├── test_tickers_endpoint.py
    └── test_tickers_portfolio_endpoint.py
```

## Running tests

```bash
# From backend/ with venv active
pytest                                      # full suite + coverage report
pytest tests/unit/ -v                       # unit tests only
pytest tests/integration/ -v               # integration tests only
pytest tests/unit/services/test_scoring.py # single file
pytest -k "health"                          # by keyword
```

## Key fixtures (`conftest.py`)

| Fixture        | Scope    | Description                                                     |
| -------------- | -------- | --------------------------------------------------------------- |
| `async_client` | function | `httpx.AsyncClient` pointed at the test app via `ASGITransport` |
| `db_session`   | function | Async SQLAlchemy session against the test database              |

## Rules

- **Unit tests** mock all I/O — database, HTTP clients, external APIs.
- **Integration tests** use a real test database (`atlas_test`) and the full ASGI app.
- Test names are sentences: `test_health_endpoint_returns_ok_status`.
- One concept per test function.
- Never copy-paste fixtures — add shared ones to `conftest.py`.
