# models/ — SQLAlchemy ORM Models

Pure SQLAlchemy 2.0 async models. No Pydantic, no service imports.

## Models

| Model             | Table              | Description                                                  |
| ----------------- | ------------------ | ------------------------------------------------------------ |
| `Ticker`          | `tickers`          | Portfolio holdings — symbol, shares, market data, cluster FK |
| `PortfolioConfig` | `portfolio_config` | Single-row config — cash balance, cash floor %               |
| `Cluster`         | `clusters`         | Position groupings — name, hex colour                        |
| `WatchlistItem`   | `watchlist`        | Tickers being monitored — symbol, market data                |

## Relationships

```
Cluster (1) ──< Ticker (many)   — cluster_id FK, nullable (unassigned = null)
PortfolioConfig                 — singleton row, no FK relationships
WatchlistItem                   — independent, no FK relationships
```

## Layering rules

- Models are **pure SQLAlchemy** — no Pydantic, no service logic, no business calculations.
- All columns are typed with SQLAlchemy 2.0 `Mapped[T]` annotations.
- Relationships use `relationship()` with `lazy="selectin"` for async-safe eager loading.
- Any schema change requires an Alembic migration — see `db/README.md`.
