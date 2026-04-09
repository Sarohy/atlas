# services/ — Business Logic Layer

All domain logic lives here. Services are called by route handlers in `api/` and call models/db directly.

## Services

### `auth.py` — `AuthService`

Handles user authentication. Verifies email/password against stored credentials.  
**Dependencies:** database session  
**Called by:** `api/v1/auth.py`

---

### `ticker_service.py` — `TickerService`

CRUD operations for portfolio tickers.  
**Methods:**

- `list_tickers()` → `list[TickerResponse]` — all tickers ordered by symbol
- `get_by_ticker(ticker)` → `TickerResponse | None`
- `create_ticker(data)` → `TickerResponse`
- `update_shares(id, shares, cluster_id)` → `TickerResponse | None`
- `delete_ticker(id)` → `bool`

**Dependencies:** database session  
**Called by:** `api/v1/tickers.py`, `api/v1/portfolio.py`

---

### `portfolio_service.py` — `PortfolioService` + `compute_portfolio_summary()`

Manages the `PortfolioConfig` row (cash balance, floor %). Also contains the pure function `compute_portfolio_summary()` that derives NAV, deployed value, deployable cash, and portfolio beta from a ticker list and config.  
**Methods:**

- `get_or_create_config()` → `CashResponse`
- `update_cash(data)` → `CashResponse`
- `adjust_cash(data)` → `CashResponse` (delta-based, clamped at 0)
- `compute_portfolio_summary(tickers, config)` → `PortfolioSummaryResponse` _(pure function)_

**Dependencies:** database session  
**Called by:** `api/v1/portfolio.py`

---

### `cluster_service.py` — `ClusterService`

CRUD for position clusters. On delete, orphaned tickers are automatically unassigned.  
**Methods:**

- `list_clusters()` → `list[ClusterResponse]`
- `create_cluster(data)` → `ClusterResponse`
- `update_cluster(id, data)` → `ClusterResponse | None`
- `delete_cluster(id)` → `bool`

**Dependencies:** database session  
**Called by:** `api/v1/clusters.py`

---

### `market_data_service.py` — `MarketDataService`

Fetches live quotes from Polygon.io and writes them back to the database. Used by both tickers and watchlist sync endpoints.  
**Methods:**

- `sync_tickers()` → `list[TickerResponse]`
- `sync_watchlist_items()` → `list[WatchlistItemResponse]`

**Dependencies:** database session, `httpx.AsyncClient`, Polygon API key  
**Called by:** `api/v1/tickers.py` (`/sync`), `api/v1/watchlist.py` (`/sync`)

---

### `watchlist_service.py` — `WatchlistService`

CRUD operations for watchlist items.  
**Methods:**

- `list_items()` → `list[WatchlistItemResponse]`
- `get_by_ticker(ticker)` → `WatchlistItemResponse | None`
- `create_item(data)` → `WatchlistItemResponse`
- `delete_item(id)` → `bool`

**Dependencies:** database session  
**Called by:** `api/v1/watchlist.py`

---

### `ticker_search_service.py` — `TickerSearchService`

Proxies the Polygon.io reference ticker search API. Returns a filtered list of active tickers matching a query string.  
**Methods:**

- `search(query)` → `list[TickerSearchResult]`

**Dependencies:** `httpx.AsyncClient`, Polygon API key  
**Called by:** `api/v1/ticker_search.py`

---

## Layering rules

- Services import from `models/`, `schemas/`, `db/`, and `core/` only.
- Services **never** import from `api/`.
- External HTTP calls (Polygon) are async only — use `httpx.AsyncClient`.
- Database access is async only — `await session.execute(...)`.
