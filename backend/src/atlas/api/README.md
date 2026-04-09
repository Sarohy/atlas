# api/ — HTTP Layer

This layer contains **only** FastAPI route handlers. Zero business logic lives here.

## Structure

```
api/
├── deps.py        — shared FastAPI Depends() factories (db session, auth service)
└── v1/
    ├── router.py       — aggregates all v1 sub-routers
    ├── health.py       — GET /health
    ├── auth.py         — POST /auth/sign-in, POST /auth/logout
    ├── tickers.py      — CRUD + sync for portfolio tickers
    ├── ticker_search.py — GET /tickers/search
    ├── portfolio.py    — summary, cash read/write/adjust
    ├── clusters.py     — CRUD for position clusters
    └── watchlist.py    — add/remove/sync watchlist items
```

## Layering rules

- Route handlers call **services only** — never the ORM directly.
- No business logic, no math, no data transformations.
- `deps.py` is the only place that wires `Depends()` factories.
- All request/response bodies use Pydantic schemas from `schemas/`.

## Full endpoint reference

See [v1/README.md](v1/README.md) for every endpoint with request/response JSON examples.
