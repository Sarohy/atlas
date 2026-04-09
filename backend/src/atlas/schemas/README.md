# schemas/ — Pydantic Request/Response Schemas

Pure Pydantic v2 models used as FastAPI request bodies and response shapes. No ORM imports, no service imports.

## Schema files

### `health.py`

| Schema           | Used as  | Fields                        |
| ---------------- | -------- | ----------------------------- |
| `HealthResponse` | Response | `status: str`, `service: str` |

---

### `auth.py`

| Schema           | Used as      | Fields                             |
| ---------------- | ------------ | ---------------------------------- |
| `SignInRequest`  | Request body | `email: EmailStr`, `password: str` |
| `SignInResponse` | Response     | `email: str`, `message: str`       |
| `LogoutResponse` | Response     | `message: str`                     |

---

### `ticker.py`

| Schema               | Used as              | Fields                                                                                                              |
| -------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `TickerCreate`       | Request body         | `ticker: str`, `shares: float`, `cluster_id: int \| None`                                                           |
| `TickerUpdate`       | Request body (PATCH) | `shares: float \| None`, `cluster_id: int \| None`                                                                  |
| `TickerResponse`     | Response             | `id`, `ticker`, `company_name`, `shares`, `cluster_id`, `price`, `day_change_pct`, `market_value`, `weight`, `beta` |
| `TickerSearchResult` | Response             | `ticker: str`, `name: str`                                                                                          |

---

### `portfolio.py`

| Schema                     | Used as                    | Fields                                                                                                       |
| -------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `CashUpdateRequest`        | Request body (PUT)         | `cash_balance: float`, `cash_floor_pct: float`                                                               |
| `CashAdjustRequest`        | Request body (POST adjust) | `amount: float`                                                                                              |
| `CashResponse`             | Response                   | `cash_balance: float`, `cash_floor_pct: float`                                                               |
| `PortfolioSummaryResponse` | Response                   | `nav`, `invested_value`, `cash_balance`, `cash_floor`, `deployable_cash`, `portfolio_beta`, `position_count` |

---

### `cluster.py`

| Schema            | Used as              | Fields                                                     |
| ----------------- | -------------------- | ---------------------------------------------------------- |
| `ClusterCreate`   | Request body         | `name: str`, `color: str` (hex)                            |
| `ClusterUpdate`   | Request body (PATCH) | `name: str \| None`, `color: str \| None`                  |
| `ClusterResponse` | Response             | `id: int`, `name: str`, `color: str`, `tickers: list[str]` |

---

### `watchlist.py`

| Schema                  | Used as      | Fields                                                    |
| ----------------------- | ------------ | --------------------------------------------------------- |
| `WatchlistItemCreate`   | Request body | `ticker: str`                                             |
| `WatchlistItemResponse` | Response     | `id`, `ticker`, `company_name`, `price`, `day_change_pct` |

---

## Layering rules

- Schemas are **pure Pydantic** — zero SQLAlchemy, zero service imports.
- Use `model_config = ConfigDict(from_attributes=True)` on response schemas to support ORM → Pydantic coercion.
- Validation errors are automatically returned as `422 Unprocessable Entity` by FastAPI.
