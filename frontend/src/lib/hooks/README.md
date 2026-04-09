# lib/hooks/ — TanStack Query Hooks

The only layer that calls `lib/api/` from within the React component tree.

## Hooks

### `use-health.ts`

| Hook          | Returns                          | Description                   |
| ------------- | -------------------------------- | ----------------------------- |
| `useHealth()` | `{ status, isLoading, isError }` | Polls backend health endpoint |

---

### `use-tickers.ts`

| Hook                | Returns                                 | Description                                     |
| ------------------- | --------------------------------------- | ----------------------------------------------- |
| `useTickers()`      | `{ data: TickerResponse[], isLoading }` | All portfolio tickers, auto-refetches           |
| `useCreateTicker()` | `{ mutate, isPending }`                 | POST /tickers — invalidates tickers query       |
| `useUpdateTicker()` | `{ mutate, isPending }`                 | PATCH /tickers/:id — invalidates tickers query  |
| `useDeleteTicker()` | `{ mutate, isPending }`                 | DELETE /tickers/:id — invalidates tickers query |
| `useSyncTickers()`  | `{ mutate, isPending }`                 | POST /tickers/sync                              |

---

### `use-ticker-search.ts`

| Hook                     | Returns                                      | Description                                                  |
| ------------------------ | -------------------------------------------- | ------------------------------------------------------------ |
| `useTickerSearch(query)` | `{ data: TickerSearchResult[], isFetching }` | Debounced autocomplete — only fires when `query.length >= 1` |

---

### `use-portfolio.ts`

| Hook                    | Returns                                         | Description                 |
| ----------------------- | ----------------------------------------------- | --------------------------- |
| `usePortfolioSummary()` | `{ data: PortfolioSummaryResponse, isLoading }` | NAV + cash breakdown        |
| `useCash()`             | `{ data: CashResponse, isLoading }`             | Current cash balance        |
| `useUpdateCash()`       | `{ mutate, isPending }`                         | PUT /portfolio/cash         |
| `useAdjustCash()`       | `{ mutate, isPending }`                         | POST /portfolio/cash/adjust |

---

### `use-clusters.ts`

| Hook                 | Returns                                  | Description               |
| -------------------- | ---------------------------------------- | ------------------------- |
| `useClusters()`      | `{ data: ClusterResponse[], isLoading }` | All clusters with tickers |
| `useCreateCluster()` | `{ mutate, isPending }`                  | POST /clusters            |
| `useUpdateCluster()` | `{ mutate, isPending }`                  | PATCH /clusters/:id       |
| `useDeleteCluster()` | `{ mutate, isPending }`                  | DELETE /clusters/:id      |

---

### `use-watchlist.ts`

| Hook                       | Returns                                        | Description           |
| -------------------------- | ---------------------------------------------- | --------------------- |
| `useWatchlist()`           | `{ data: WatchlistItemResponse[], isLoading }` | All watchlist items   |
| `useAddToWatchlist()`      | `{ mutate, isPending }`                        | POST /watchlist       |
| `useRemoveFromWatchlist()` | `{ mutate, isPending }`                        | DELETE /watchlist/:id |
| `useSyncWatchlist()`       | `{ mutate, isPending }`                        | POST /watchlist/sync  |

---

## Rules

- Hooks are the **only** place that calls `lib/api/` functions from within the React tree.
- Every mutation hook must call `queryClient.invalidateQueries(...)` on success to keep UI in sync.
- All hooks must be covered by tests in `tests/unit/` using MSW to intercept requests.
- No business logic in hooks — transform data in `lib/api/` or `lib/schemas/`.
