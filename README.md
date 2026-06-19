# ATLAS — Active Investing Decision-Support Tool

ATLAS helps a single investor evaluate conviction scores, apply regime modifiers, and maintain an auditable decision trace. It never executes trades autonomously. Safety and auditability are first-class constraints.

## What's been built

### Frameworks implemented

| Framework | Name | Status |
|-----------|------|--------|
| F1 | Momentum Score | ✅ Live |
| F2 | Earnings Gate | ✅ Live |
| F3 | Analyst Consensus | ✅ Live |
| F4 | Options Flow | ✅ Live |
| F5 | Fundamental Quality | ✅ Live |
| F6 | Framework Score (conviction 0–100) | ✅ Live |
| F7 | Earnings Gate (earnings proximity guard) | ✅ Live |
| F8 | Position Sizing | ✅ Live |
| F9 | Options Flow Engine (UW + Polygon + dark pool) | ✅ Live |
| F10 | LEAPS Strategy (entry eligibility) | ✅ Live |
| F11 | Cash Floor Enforcer | ✅ Live |
| F12 | Catalyst No-Fly Zone | ✅ Live |
| F13 | Tranche Sizing | ✅ Live |
| F14 | Conviction Action | ✅ Live |
| F29 | Regime Modifier (VIX / Brent / escalation) | ✅ Live |
| F30 | Portfolio Health | ✅ Live |

### Architecture

```
atlas/
├── backend/          FastAPI + PostgreSQL (Python 3.12+, uv)
├── frontend/         Next.js 16 App Router (Node 22+, pnpm)
├── .claude/agents/   Sub-agent definitions (architecture, TDD, review)
├── AGENTS.md         Authoritative AI agent coding instructions
├── BACKEND_SETUP.md
└── FRONTEND_SETUP.md
```

**Backend layers** (strict top-down, never reverse):
```
api/       routes only — no business logic
services/  business logic — calls db and external clients
models/    SQLAlchemy ORM models — pure
schemas/   Pydantic request/response — pure
db/        session, base, migrations
core/      cross-cutting (logging, security, settings)
```

**Frontend layers**:
```
app/           Server Components by default; 'use client' only when needed
components/    imports from lib/ only — no raw fetch calls
lib/api/       all fetch calls
lib/hooks/     TanStack Query hooks — only layer calling lib/api/
lib/schemas/   pure Zod — no external imports
lib/stores/    Zustand stores
```

### Key safety rules

- **Decision Trace is append-only.** Every block, override, and deferral is permanently logged. No `UPDATE` or `DELETE` ever.
- **Regime modifier is a pure function.** No side effects, no I/O, no randomness.
- **Conviction scores are read-only intraday.** No recomputation outside the post-close batch job.
- **Framework 12 no-fly zone uses conservative defaults.** When any data source is unavailable, all sell-side actions (covered calls, partial sells, trims) are treated as BLOCKED.
- **F4b universe governance + DRAM policy is documented in spec.** See `docs/extension-washout-spec-v2.2-amendment.md` §6 for official framing, alert-universe dedupe requirements, ETF-flow limits, and leveraged-product handling.

### Database tables

| Table | Purpose |
|-------|---------|
| `tickers` | Held portfolio positions |
| `watchlist` | Watchlist tickers |
| `leaps_eligibility` | LEAPS strategy tracking |
| `nav_history` | NAV history for cash floor |
| `clusters` | Sector/cluster groupings |
| `gtc_orders` | GTC order tracking (F11) |
| `signal_queue` | Queued buy signals (F11) |
| `catalyst_events` | Non-earnings catalyst events (F12) |
| `framework12_overrides` | Per-action human overrides (F12) |
| `decision_trace` | Append-only audit log (F12) |
| `atlas_config` | Runtime config key-value store |

### Config (never hardcoded in app code)

| Key | Value | Purpose |
|-----|-------|---------|
| `f12_catalyst_window_days` | 7 | F12 no-fly zone window in calendar days |
| `f12_exit_deferral_trading_days` | 10 | Trading days after catalyst before exit rule resumes |

## Running locally

### Backend

```bash
# PostgreSQL must be running first
cd backend
cp .env.example .env          # fill in DATABASE_URL and API keys
uv run uvicorn atlas.main:create_app --factory --reload --port 8000
```

Required env:
```
DATABASE_URL=postgresql+asyncpg://localhost/atlas_dev
ENVIRONMENT=development
ALPHAVANTAGE_API_KEY=...
POLYGON_API_KEY=...
```

Run migrations after first start:
```bash
cd backend && uv run alembic upgrade head
```

### Frontend

```bash
cd frontend
cp .env.example .env.local    # set NEXT_PUBLIC_API_URL
pnpm dev                      # http://localhost:3000
```

Required env:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Tests

```bash
# Backend
cd backend && uv run pytest --cov=src --cov-fail-under=90

# Frontend unit + component
cd frontend && pnpm test

# Frontend e2e (requires backend on :8000)
cd frontend && pnpm test:e2e
```

## Quality gate (must pass before every commit)

### Backend
```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=90
```

### Frontend
```bash
cd frontend
pnpm typecheck        # tsc --noEmit
pnpm lint
pnpm format:check
pnpm test:coverage    # ≥90% coverage
```

## Tech stack

**Backend:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 async · PostgreSQL · Alembic · pytest · uv · ruff · mypy · structlog

**Frontend:** Next.js 16 · TypeScript 5 strict · Tailwind CSS 4 · shadcn/ui · TanStack Query v5 · Zustand · Zod v4 · React Hook Form · Vitest · MSW · Playwright · pnpm

## Sub-agents (`.claude/agents/`)

| Agent | When to invoke |
|-------|---------------|
| `architecture-guardian` | Before adding any new module, file, directory, or dependency |
| `tdd-enforcer` | At the start of every feature, bug fix, or refactor touching business logic |
| `code-reviewer` | After any implementation work, before committing |

## Commit convention

```
<type>(<scope>): <short description>
```
Types: `feat` · `fix` · `refactor` · `test` · `chore` · `docs` · `perf` · `ci`  
Scopes: `backend` · `frontend` · `infra` · `deps` · `agents`
