# API v1 — Endpoint Reference

Base path: `/api/v1`  
All responses are JSON. All timestamps are ISO 8601 UTC.

---

## Health

### GET /api/v1/health

**Description:** Returns service liveness status. Used by the frontend `HealthStatus` component and load balancers.  
**Auth required:** No

#### Response `200 OK`

```json
{
  "status": "ok",
  "service": "atlas-backend"
}
```

---

## Auth

### POST /api/v1/auth/sign-in

**Description:** Authenticates a user by email and password.  
**Auth required:** No

#### Request body

```json
{
  "email": "user@example.com",
  "password": "s3cur3p@ss"
}
```

#### Response `200 OK`

```json
{
  "email": "user@example.com",
  "message": "Sign in successful."
}
```

#### Error responses

| Status | When                      |
| ------ | ------------------------- |
| 401    | Invalid email or password |

---

### POST /api/v1/auth/logout

**Description:** Returns a logout confirmation for frontend session cleanup. Stateless — no server session is invalidated.  
**Auth required:** No

#### Response `200 OK`

```json
{
  "message": "Logout successful."
}
```

---

## Tickers (Portfolio)

### GET /api/v1/tickers

**Description:** Returns all saved portfolio tickers ordered by symbol.  
**Auth required:** No

#### Response `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "shares": 10.5,
    "cluster_id": 2,
    "price": 213.49,
    "day_change_pct": 1.23,
    "market_value": 2241.65,
    "weight": 0.12,
    "beta": 1.21
  }
]
```

---

### POST /api/v1/tickers

**Description:** Adds a new ticker/share-count pair to the portfolio.  
**Auth required:** No

#### Request body

```json
{
  "ticker": "MSFT",
  "shares": 5,
  "cluster_id": null
}
```

#### Response `201 Created`

```json
{
  "id": 2,
  "ticker": "MSFT",
  "company_name": "Microsoft Corp.",
  "shares": 5,
  "cluster_id": null,
  "price": null,
  "day_change_pct": null,
  "market_value": null,
  "weight": null,
  "beta": null
}
```

#### Error responses

| Status | When                               |
| ------ | ---------------------------------- |
| 409    | Ticker already exists in portfolio |

---

### PATCH /api/v1/tickers/{ticker_id}

**Description:** Updates the share count and/or cluster assignment for an existing ticker.  
**Auth required:** No

#### Request body (all fields optional)

```json
{
  "shares": 7.5,
  "cluster_id": 3
}
```

#### Response `200 OK`

```json
{
  "id": 2,
  "ticker": "MSFT",
  "company_name": "Microsoft Corp.",
  "shares": 7.5,
  "cluster_id": 3,
  "price": 415.2,
  "day_change_pct": -0.45,
  "market_value": 3114.0,
  "weight": 0.08,
  "beta": 0.95
}
```

#### Error responses

| Status | When                |
| ------ | ------------------- |
| 404    | Ticker ID not found |

---

### DELETE /api/v1/tickers/{ticker_id}

**Description:** Removes a ticker from the portfolio.  
**Auth required:** No

#### Response `204 No Content`

_(empty body)_

#### Error responses

| Status | When                |
| ------ | ------------------- |
| 404    | Ticker ID not found |

---

### POST /api/v1/tickers/sync

**Description:** Fetches live quotes from Polygon.io and updates all ticker market-data fields (price, day change, beta). Returns the full updated ticker list.  
**Auth required:** No

#### Response `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "shares": 10.5,
    "cluster_id": 2,
    "price": 213.49,
    "day_change_pct": 1.23,
    "market_value": 2241.65,
    "weight": 0.12,
    "beta": 1.21
  }
]
```

#### Error responses

| Status | When                             |
| ------ | -------------------------------- |
| 503    | `POLYGON_API_KEY` not configured |

---

### GET /api/v1/tickers/search?q={query}

**Description:** Searches active tickers via the Polygon.io reference API. Used by the Add Ticker dialog autocomplete.  
**Auth required:** No

#### Query parameters

| Param | Type   | Required | Description                                     |
| ----- | ------ | -------- | ----------------------------------------------- |
| `q`   | string | ✅       | Ticker symbol or company name (min 1 character) |

#### Response `200 OK`

```json
[
  {
    "ticker": "AAPL",
    "name": "Apple Inc."
  }
]
```

#### Error responses

| Status | When                             |
| ------ | -------------------------------- |
| 503    | `POLYGON_API_KEY` not configured |

---

## Portfolio

### GET /api/v1/portfolio/summary

**Description:** Returns the computed portfolio summary — NAV, cash breakdown, portfolio beta, and deployable cash.  
**Auth required:** No

#### Response `200 OK`

```json
{
  "nav": 25000.0,
  "invested_value": 22000.0,
  "cash_balance": 3000.0,
  "cash_floor": 500.0,
  "deployable_cash": 2500.0,
  "portfolio_beta": 1.08,
  "position_count": 12
}
```

---

### GET /api/v1/portfolio/cash

**Description:** Returns the current cash balance and floor percentage.  
**Auth required:** No

#### Response `200 OK`

```json
{
  "cash_balance": 3000.0,
  "cash_floor_pct": 5.0
}
```

---

### PUT /api/v1/portfolio/cash

**Description:** Replaces the cash balance and floor percentage.  
**Auth required:** No

#### Request body

```json
{
  "cash_balance": 5000.0,
  "cash_floor_pct": 5.0
}
```

#### Response `200 OK`

```json
{
  "cash_balance": 5000.0,
  "cash_floor_pct": 5.0
}
```

---

### POST /api/v1/portfolio/cash/adjust

**Description:** Adjusts the cash balance by a delta. Positive = deposit, negative = withdrawal. Balance is clamped at zero.  
**Auth required:** No

#### Request body

```json
{
  "amount": -500.0
}
```

#### Response `200 OK`

```json
{
  "cash_balance": 4500.0,
  "cash_floor_pct": 5.0
}
```

---

## Clusters

### GET /api/v1/clusters

**Description:** Returns all clusters with their assigned tickers.  
**Auth required:** No

#### Response `200 OK`

```json
[
  {
    "id": 1,
    "name": "Tech",
    "color": "#38bdf8",
    "tickers": ["AAPL", "MSFT", "NVDA"]
  }
]
```

---

### POST /api/v1/clusters

**Description:** Creates a new cluster.  
**Auth required:** No

#### Request body

```json
{
  "name": "Energy",
  "color": "#fbbf24"
}
```

#### Response `201 Created`

```json
{
  "id": 3,
  "name": "Energy",
  "color": "#fbbf24",
  "tickers": []
}
```

#### Error responses

| Status | When                                  |
| ------ | ------------------------------------- |
| 409    | Cluster with same name already exists |

---

### PATCH /api/v1/clusters/{cluster_id}

**Description:** Updates a cluster's name and/or colour.  
**Auth required:** No

#### Request body (all fields optional)

```json
{
  "name": "Commodities",
  "color": "#f472b6"
}
```

#### Response `200 OK`

```json
{
  "id": 3,
  "name": "Commodities",
  "color": "#f472b6",
  "tickers": ["XOM", "CVX"]
}
```

#### Error responses

| Status | When                 |
| ------ | -------------------- |
| 404    | Cluster ID not found |

---

### DELETE /api/v1/clusters/{cluster_id}

**Description:** Deletes a cluster. Tickers that belonged to it become unassigned (`cluster_id = null`).  
**Auth required:** No

#### Response `204 No Content`

_(empty body)_

#### Error responses

| Status | When                 |
| ------ | -------------------- |
| 404    | Cluster ID not found |

---

## Watchlist

### GET /api/v1/watchlist

**Description:** Returns all watchlist items ordered by symbol.  
**Auth required:** No

#### Response `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "TSLA",
    "company_name": "Tesla Inc.",
    "price": 248.5,
    "day_change_pct": 2.1
  }
]
```

---

### POST /api/v1/watchlist

**Description:** Adds a ticker to the watchlist.  
**Auth required:** No

#### Request body

```json
{
  "ticker": "TSLA"
}
```

#### Response `201 Created`

```json
{
  "id": 1,
  "ticker": "TSLA",
  "company_name": null,
  "price": null,
  "day_change_pct": null
}
```

#### Error responses

| Status | When                        |
| ------ | --------------------------- |
| 409    | Ticker already on watchlist |

---

### DELETE /api/v1/watchlist/{item_id}

**Description:** Removes a ticker from the watchlist.  
**Auth required:** No

#### Response `204 No Content`

_(empty body)_

#### Error responses

| Status | When                        |
| ------ | --------------------------- |
| 404    | Watchlist item ID not found |

---

### POST /api/v1/watchlist/sync

**Description:** Fetches live quotes from Polygon.io and updates all watchlist market-data fields.  
**Auth required:** No

#### Response `200 OK`

```json
[
  {
    "id": 1,
    "ticker": "TSLA",
    "company_name": "Tesla Inc.",
    "price": 248.5,
    "day_change_pct": 2.1
  }
]
```

#### Error responses

| Status | When                             |
| ------ | -------------------------------- |
| 503    | `POLYGON_API_KEY` not configured |
