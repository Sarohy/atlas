# lib/schemas/ — Zod Validation Schemas

Pure Zod schemas. No imports from `lib/api/` or `lib/hooks/`. Used to validate every API response before it enters the React tree.

## Schemas

### `ticker.ts`

| Schema                         | Validates                                                         |
| ------------------------------ | ----------------------------------------------------------------- |
| `tickerResponseSchema`         | Single ticker from `GET /tickers` or any ticker mutation response |
| `tickerListSchema`             | Array of tickers                                                  |
| `tickerSearchResultSchema`     | Single autocomplete result                                        |
| `tickerSearchResultListSchema` | Array of search results                                           |

---

### `portfolio.ts`

| Schema                   | Validates                          |
| ------------------------ | ---------------------------------- |
| `portfolioSummarySchema` | `GET /portfolio/summary` response  |
| `cashResponseSchema`     | `GET/PUT /portfolio/cash` response |

---

### `cluster.ts`

| Schema                  | Validates                        |
| ----------------------- | -------------------------------- |
| `clusterResponseSchema` | Single cluster with tickers list |
| `clusterListSchema`     | Array of clusters                |

---

### `watchlist.ts`

| Schema                | Validates                |
| --------------------- | ------------------------ |
| `watchlistItemSchema` | Single watchlist item    |
| `watchlistListSchema` | Array of watchlist items |

---

### `health.ts`

| Schema         | Validates                                    |
| -------------- | -------------------------------------------- |
| `healthSchema` | `GET /health` response `{ status, service }` |

---

### `auth.ts`

| Schema                 | Validates                     |
| ---------------------- | ----------------------------- |
| `signInResponseSchema` | `POST /auth/sign-in` response |

---

## Rules

- Schemas are **pure Zod** — no API calls, no hooks, no side effects.
- Every schema must export a TypeScript type inferred via `z.infer<typeof schema>`.
- `lib/api/` functions call `schema.parse(response)` before returning — never trust raw JSON.
- Schema tests live in `tests/unit/lib/schemas/`.
