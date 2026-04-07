# ATLAS — Coding Instructions for AI Agents

> This document is the authoritative guide for every AI agent working in this repository.
> Read it fully before touching any file. It overrides any assumptions from training data.

---

## 1. Project overview

ATLAS is a **decision-support tool for active investing**. It helps a single investor evaluate
conviction scores, apply regime modifiers, and maintain an auditable decision trace — it never
executes trades autonomously. Safety and auditability are first-class constraints.

**Monorepo layout**

```
atlas/
├── backend/          FastAPI + PostgreSQL (Python 3.12+, uv)
├── frontend/         Next.js 16 App Router (Node 22+, pnpm)
├── .claude/agents/   Sub-agent definitions (architecture, TDD, review)
├── AGENTS.md         ← this file
├── README.md
├── BACKEND_SETUP.md
└── FRONTEND_SETUP.md
```

---

## 2. Non-negotiable rules

These apply to every change, every file, every agent:

| Rule | Detail |
|---|---|
| **TDD first** | Write a failing test before any implementation. No exceptions. |
| **No secrets in code** | Use env vars / config. `.env` is gitignored. |
| **No `any`** | TypeScript `any` and Python implicit `Any` are both banned. |
| **No magic numbers** | Use named constants with a comment explaining the value. |
| **No commented-out code** | Delete it. Git is the history. |
| **No `TODO` without a ticket** | `TODO(#42): ...` is fine. Plain `TODO` is not. |
| **Functions do one thing** | Flag any function over 40 lines for splitting. |
| **Decision trace is append-only** | Never `UPDATE` or `DELETE` from audit/trace tables. |

---

## 3. Tech stack at a glance

### Backend — `backend/`

| Concern | Tool |
|---|---|
| Runtime | Python 3.12+ (managed by pyenv + uv) |
| Framework | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2 (async only — `asyncpg` driver) |
| Migrations | Alembic (async) |
| Logging | structlog (JSON in prod, console in dev) |
| Tests | pytest + pytest-asyncio + pytest-cov |
| Lint / format | ruff |
| Types | mypy (strict) |
| Dev runner | `uv run` |

### Frontend — `frontend/`

| Concern | Tool |
|---|---|
| Runtime | Node 22+ (managed by nvm) |
| Framework | Next.js 16 App Router |
| Language | TypeScript 5 strict |
| Styling | Tailwind CSS 4 |
| UI primitives | shadcn/ui + Radix UI |
| Server state | TanStack Query v5 |
| Client state | Zustand |
| Forms | React Hook Form + Zod resolver |
| Validation | Zod v4 |
| Unit tests | Vitest + Testing Library + MSW |
| E2E tests | Playwright (Chromium only) |
| Lint | ESLint flat config |
| Format | Prettier |
| Package manager | pnpm |

---

## 4. Architecture & layering

### Backend (strict top-down, never reverse)

```
api/         routes only — no business logic
services/    business logic — calls db and external clients
models/      SQLAlchemy ORM models — pure, no schemas or services
schemas/     Pydantic request/response — pure, no models or services
db/          session, base, migrations infra
core/        cross-cutting (logging, security, settings) — imported by all, imports nothing above
```

Verify import direction with `grep` before adding a cross-layer import.

### Frontend (strict call direction)

```
app/           Server Components by default; 'use client' only when hooks/interactivity needed
components/    may import from lib/ — never make raw fetch calls
lib/api/       all fetch calls live here
lib/hooks/     only layer that calls lib/api/ from the React tree
lib/schemas/   pure Zod — no imports from lib/api/ or lib/hooks/
lib/stores/    Zustand stores (when needed)
lib/utils.ts   small pure helpers only; split at 100 lines
types/         shared TypeScript types
```

---

## 5. TDD workflow (enforced by `tdd-enforcer` agent)

```
RED   → write a failing test that describes the behavior
GREEN → write minimum code to pass it
REFACTOR → clean up; keep tests green
```

1. Locate or create the test file **first**.
2. Run the test to confirm it fails for the right reason (assertion error, not import error).
3. Write the implementation.
4. Run the full suite — coverage must stay **≥ 90%**.

Backend test structure mirrors source:
```
backend/tests/unit/services/test_scoring.py  ↔  backend/src/atlas/services/scoring.py
```

Frontend test structure mirrors source:
```
frontend/tests/unit/lib/api-client.test.ts   ↔  frontend/src/lib/api/client.ts
frontend/tests/components/health-status.test.tsx  ↔  frontend/src/components/health-status.tsx
```

---

## 6. Quality gate — must pass before every commit

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
pnpm lint             # eslint src tests
pnpm format:check     # prettier --check
pnpm test:coverage    # vitest run + v8 coverage ≥ 90%
```

Git hooks (Husky + lint-staged on frontend, pre-commit on backend) enforce this automatically.

---

## 7. Running the project locally

### Backend

```bash
# Terminal 1 — PostgreSQL must be running first
cd backend
uv run uvicorn atlas.main:create_app --factory --reload --port 8000
```

Required env (copy from `backend/.env.example` → `backend/.env`):
```
DATABASE_URL=postgresql+asyncpg://localhost/atlas_dev
ENVIRONMENT=development
```

### Frontend

```bash
# Terminal 2 — requires backend on :8000 for real API calls
cd frontend
pnpm dev              # http://localhost:3000
```

Required env (copy from `frontend/.env.example` → `frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Tests

```bash
# Backend unit + integration (no running server needed)
cd backend && uv run pytest

# Frontend unit + component (MSW mocks the backend)
cd frontend && pnpm test

# E2E (requires backend on :8000; Playwright auto-starts pnpm dev on :3000)
cd frontend && pnpm test:e2e
```

---

## 8. Git conventions

### Commit message format

```
<type>(<scope>): <short description>

[optional body]
[optional footer]
```

**Types:** `feat` | `fix` | `refactor` | `test` | `chore` | `docs` | `perf` | `ci`  
**Scope:** `backend` | `frontend` | `infra` | `deps` | `agents` (or a module name)

**Examples:**
```
feat(backend): add conviction score endpoint
fix(frontend): handle empty portfolio in HealthStatus
test(backend): add unit tests for regime modifier
chore(deps): bump fastapi to 0.136.0
```

Rules:
- Imperative mood, present tense: "add" not "added"
- No period at the end of the subject line
- Subject line ≤ 72 characters
- Reference issues: `Closes #42` in the footer

---

## 9. ATLAS-specific safety rules

These are business-domain constraints — violating them is a blocking issue.

### Decision Trace immutability
Any code that writes to the decision trace log must be **append-only**. No `UPDATE` or `DELETE`
on audit or trace tables/endpoints. Flag immediately if you see one.

### Safety-critical confirmation flows
Any code touching trade execution, framework override, or position changes must have a
corresponding e2e test covering the typed-confirmation path before it can be merged.

### Regime modifier purity
Code computing regime state (Crisis Halt / Caution / Clear from VIX, Brent, escalation prob)
must be a **pure function** — no side effects, no I/O, no randomness. Unit test it as such.

### Conviction scores are read-only intraday
No code path may recompute or mutate a conviction score outside the post-close batch job.

---

## 10. Sub-agents available in `.claude/agents/`

| Agent | When to invoke |
|---|---|
| `architecture-guardian` | Before adding any new module, file, directory, or dependency |
| `tdd-enforcer` | At the start of every feature, bug fix, or refactor touching business logic |
| `code-reviewer` | After any implementation work, before committing |

---

## 11. What agents must NOT do

- Do not write implementation code before a failing test exists.
- Do not commit with failing lint, type checks, or tests.
- Do not add a dependency not on the approved list without justification.
- Do not write raw SQL that bypasses SQLAlchemy models (unless in a migration).
- Do not use `fetch` directly in React components — route it through `lib/api/` and `lib/hooks/`.
- Do not add `// @ts-ignore` or `# type: ignore` without an inline comment explaining exactly why.
- Do not create new top-level directories without discussing with the architecture-guardian first.
