# lib/api/ — API Client Functions

All `fetch` calls to the backend live here. Components and hooks never call `fetch` directly.

## Base URL

Read from `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000`).  
All functions prepend `/api/v1/` to the path.

## Functions by module

### `atlas-shell.ts` (or equivalent client file)

| Function                  | Method | Endpoint                        | Description             |
| ------------------------- | ------ | ------------------------------- | ----------------------- |
| `fetchHealth()`           | GET    | `/api/v1/health`                | Liveness check          |
| `signIn(email, password)` | POST   | `/api/v1/auth/sign-in`          | Authenticate user       |
| `logout()`                | POST   | `/api/v1/auth/logout`           | Session cleanup         |
| `fetchTickers()`          | GET    | `/api/v1/tickers`               | All portfolio tickers   |
| `createTicker(data)`      | POST   | `/api/v1/tickers`               | Add ticker to portfolio |
| `updateTicker(id, data)`  | PATCH  | `/api/v1/tickers/:id`           | Update shares/cluster   |
| `deleteTicker(id)`        | DELETE | `/api/v1/tickers/:id`           | Remove ticker           |
| `syncTickers()`           | POST   | `/api/v1/tickers/sync`          | Refresh market data     |
| `searchTickers(q)`        | GET    | `/api/v1/tickers/search?q=`     | Autocomplete search     |
| `fetchPortfolioSummary()` | GET    | `/api/v1/portfolio/summary`     | NAV + cash breakdown    |
| `fetchCash()`             | GET    | `/api/v1/portfolio/cash`        | Cash balance + floor    |
| `updateCash(data)`        | PUT    | `/api/v1/portfolio/cash`        | Set cash balance        |
| `adjustCash(amount)`      | POST   | `/api/v1/portfolio/cash/adjust` | Delta cash update       |
| `fetchClusters()`         | GET    | `/api/v1/clusters`              | All clusters            |
| `createCluster(data)`     | POST   | `/api/v1/clusters`              | New cluster             |
| `updateCluster(id, data)` | PATCH  | `/api/v1/clusters/:id`          | Rename/recolour         |
| `deleteCluster(id)`       | DELETE | `/api/v1/clusters/:id`          | Remove cluster          |
| `fetchWatchlist()`        | GET    | `/api/v1/watchlist`             | All watchlist items     |
| `addToWatchlist(ticker)`  | POST   | `/api/v1/watchlist`             | Add ticker to watchlist |
| `removeFromWatchlist(id)` | DELETE | `/api/v1/watchlist/:id`         | Remove from watchlist   |
| `syncWatchlist()`         | POST   | `/api/v1/watchlist/sync`        | Refresh watchlist data  |

## Rules

- Every function must have explicit TypeScript return types — no `any`.
- All responses are validated through the Zod schemas in `lib/schemas/` before being returned.
- Throw typed errors on non-2xx responses — never silently return `undefined`.
- No business logic here — pure HTTP translation layer.

## Full backend API reference

See [backend/src/atlas/api/v1/README.md](../../../../backend/src/atlas/api/v1/README.md) for complete request/response JSON documentation.
