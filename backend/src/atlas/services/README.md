# Services Layer Guide

This folder contains backend business-logic services for ATLAS.

## Purpose

- Keep API routes thin and focused on HTTP concerns.
- Centralize business rules, orchestration, and external integrations.
- Isolate pure scoring logic into testable helpers.
- Keep database access through SQLAlchemy session-aware service classes.

## File-by-file overview

### Core CRUD and account services

- `auth.py`
  - `AuthService` authenticates users using email/password and active status checks.
  - Reads `User` records through async SQLAlchemy.

- `ticker_service.py`
  - `TickerService` manages portfolio tickers.
  - Supports list/get/create/update/delete for `Ticker` records.

- `watchlist_service.py`
  - `WatchlistService` manages watchlist items.
  - Supports list/get/create/delete for `WatchlistItem` records.

- `cluster_service.py`
  - `ClusterService` manages ticker clusters.
  - Handles list/get/create/update/delete and eager loads related tickers.

- `portfolio_service.py`
  - Pure helper: `compute_portfolio_summary(...)` builds NAV, cash metrics, deployable cash, and beta views.
  - `PortfolioService` reads and updates singleton `PortfolioConfig` (cash balance + floor percent).

### Market data ingestion services

- `ticker_search_service.py`
  - `TickerSearchService` wraps Polygon ticker reference search.
  - Returns normalized `TickerSearchResult` values.

- `market_data_service.py`
  - `MarketDataService` syncs live price fields and rolling beta for both portfolio tickers and watchlist items.
  - Two-phase sync pattern:
    1. Polygon snapshot batches for current price and day-change data.
    2. Polygon daily aggregate bars for beta vs `SPY`.
  - Writes `current_price`, `previous_close`, `day_change`, `day_change_pct`, `position_value` (tickers only), `beta`, and `synced_at`.

- `market_conditions_service.py`
  - `MarketConditionsService` fetches ticker-independent regime inputs:
    - Brent latest and previous daily close.
    - VIX latest value.
  - VIX fetch uses Alpha Vantage first, then Yahoo Finance fallback.

### Framework scoring services (F1-F5 and aggregates)

- `momentum_service.py` (F1)
  - Computes momentum score from RSI, MACD, MA alignment, 52-week position, 1M/6M performance, and sector-relative 6M performance.
  - Uses Polygon bars + ticker reference metadata for sector ETF mapping.

- `earnings_service.py` (F2)
  - Computes earnings-quality score from revenue growth, EPS beat history, guidance direction, margin trajectory, and backlog visibility.
  - Uses Alpha Vantage financial endpoints and FMP earning call transcripts.

- `analyst_service.py` (F3)
  - Computes analyst-conviction score from consensus rating quality, analyst count, price-target upside, and PT revision direction.
  - Uses Benzinga + Polygon current price.

- `options_flow_service.py` (F4)
  - Computes options-flow score from whale blocks, call/put premium ratio, volume-vs-open-interest, dark pool prints, and sweep type.
  - Uses Unusual Whales endpoints.
  - Applies collar-based score cap rules.

- `fundamental_service.py` (F5)
  - Computes fundamental-quality score from insider activity, Altman Z, free cash flow trend, debt/equity, and institutional ownership.
  - Uses sec-api Form 4 data + Alpha Vantage fundamentals.
  - Applies hard-block and cap logic based on distress and insider activity.

- `framework_score_service.py`
  - `FrameworkScoreService` orchestrates F1-F5 concurrently.
  - Applies framework-level weights to produce final framework score, action, tone, and flags.
  - Degrades gracefully to neutral factor defaults when a sub-service fails.

- `regime_modifier_service.py`
  - Applies market-regime rules (Brent, VIX, active war flag) to a base framework score.
  - Computes adjusted score and cash-guidance percentages (and USD ranges when position value exists).
  - Supports using a caller-supplied base score to avoid recomputing framework score.

## External providers used in this folder

- Polygon.io
  - Ticker search, snapshots, aggregates, some price lookups.
- Alpha Vantage
  - Brent, VIX (primary), and financial statements.
- Yahoo Finance
  - VIX fallback path.
- Benzinga
  - Analyst ratings and revisions.
- Unusual Whales
  - Options flow and dark pool data.
- Financial Modeling Prep (FMP)
  - Earnings call transcripts.
- sec-api.io
  - Form 4 insider transactions.

## Design notes

- Most scoring files expose pure helper functions for deterministic unit testing.
- Service classes own network/database IO and conversion from raw payloads to schema responses.
- Framework and regime orchestration uses `asyncio.gather(...)` for concurrent fetches.
- Fallback behavior is intentional: failed upstreams should not crash score computation paths.

## Quick navigation

- CRUD + DB services: `auth.py`, `ticker_service.py`, `watchlist_service.py`, `cluster_service.py`, `portfolio_service.py`
- Market sync/search: `ticker_search_service.py`, `market_data_service.py`, `market_conditions_service.py`
- Scoring engines: `momentum_service.py`, `earnings_service.py`, `analyst_service.py`, `options_flow_service.py`, `fundamental_service.py`
- Aggregators: `framework_score_service.py`, `regime_modifier_service.py`
