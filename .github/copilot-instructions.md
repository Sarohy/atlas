# ATLAS — GitHub Copilot Instructions

You are an AI coding assistant working inside the ATLAS monorepo.
These instructions are **always active** and override any default behaviour.
Three quality agents are baked into every response you produce. You must run all three, in order, before writing or modifying any code.

---

## Agent 1 — TDD Enforcer (runs FIRST, on every feature / fix / refactor)

Before writing a single line of implementation code:

1. **Find the test file** that corresponds to the code being changed.
   - Backend: `backend/tests/unit/` or `backend/tests/integration/`
   - Frontend: `frontend/tests/unit/`, `frontend/tests/components/`, or `frontend/e2e/`
2. **If no test exists** → write the failing test first. Do not proceed to implementation until the test file is created.
3. **Confirm RED phase**: state the exact assertion that will fail.
4. Only then write the minimum implementation to pass it.
5. After implementation, confirm GREEN phase by mentally tracing the test.

**Verdicts you must emit at the top of any implementation response:**

- `🔴 RED PHASE CONFIRMED — proceeding to implementation`
- `🟢 GREEN PHASE — tests already cover this, proceeding to refactor`
- `❌ TDD VIOLATION — I will write the test first`

**Rules:**

- Never write implementation without a failing test. No exceptions.
- Test names must read as sentences: `test_health_endpoint_returns_ok_status`.
- One concept per test function.
- Coverage must stay ≥ 90%. Flag immediately if a change risks dropping it.
- Do not write tests that assert on internal implementation details when a behavioural assertion works.

---

## Agent 2 — Architecture Guardian (runs on every new file, module, or dependency)

Before creating any new file or adding any dependency:

1. **Check the layer** the file belongs in. Enforce strict top-down call direction — never reverse it.

### Backend layers (can call down, never up)

```
api/       → routes only, zero business logic
services/  → business logic; calls db and external clients
models/    → pure SQLAlchemy ORM; no schemas or services imported
schemas/   → pure Pydantic; no models or services imported
db/        → session, base, migration infra
core/      → cross-cutting (logging, security, settings); imports nothing above it
```

### Frontend layers (strict call direction)

```
app/           → Server Components by default; 'use client' only for hooks/interactivity
components/    → may import from lib/; never make raw fetch calls
lib/api/       → all fetch calls live here
lib/hooks/     → only layer that calls lib/api/ from the React tree
lib/schemas/   → pure Zod; no imports from lib/api/ or lib/hooks/
lib/stores/    → Zustand stores only
lib/utils.ts   → pure helpers only; split at 100 lines
types/         → shared TypeScript types
```

2. **Check new dependencies** against the approved lists:
   - **Approved backend:** fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, asyncpg, alembic, structlog, httpx, pytest, pytest-asyncio, pytest-cov, ruff, mypy, pre-commit
   - **Approved frontend:** next, react, typescript, tailwindcss, @tanstack/react-query, zustand, react-hook-form, @hookform/resolvers, zod, vitest, @testing-library/\*, msw, @playwright/test, prettier, eslint, lucide-react, recharts, date-fns

   Anything not on these lists: state the justification explicitly before proceeding.

3. **File naming rules:**
   - One concept per file.
   - File name matches its primary export.
   - Tests mirror source: `src/atlas/services/scoring.py` → `tests/unit/services/test_scoring.py`.
   - No new top-level directories without explicit user confirmation.

**Emit before creating any new file:**

- `✅ ARCHITECTURE OK — [layer] is correct`
- `⚠️ SUGGESTION — better location: [path]`
- `❌ ARCHITECTURE VIOLATION — [reason]; correct path is [path]`

---

## Agent 3 — Code Reviewer (runs AFTER every implementation, before presenting final code)

After writing code, self-review it against this checklist before showing it to the user.

### Universal rules

- [ ] No commented-out code — delete it, git is the history
- [ ] No bare `TODO` — must be `TODO(#<issue>): …`
- [ ] No magic numbers — use named constants with an explanatory comment
- [ ] No hardcoded URLs, secrets, or env values
- [ ] Every function does one thing; flag anything over 40 lines
- [ ] Function and variable names are descriptive — no `tmp`, `data`, `x`, `helper`

### Backend (Python / FastAPI)

- [ ] All functions have full type hints; no implicit `Any`
- [ ] Pydantic models for all request/response bodies — no raw dicts
- [ ] Route handlers delegate to services — zero business logic in routes
- [ ] Database access is async only — no sync SQLAlchemy
- [ ] No bare `except:` — catch specific exceptions
- [ ] Logging uses structlog with key-value pairs, not f-strings
- [ ] Every new endpoint → integration test; every schema → unit test; every service → unit test with mocked deps
- [ ] Migrations present for any model changes

### Frontend (TypeScript / React / Next.js)

- [ ] No `any` types; no `// @ts-ignore` without an inline explanation
- [ ] `'use client'` only when hooks or interactivity require it
- [ ] All API calls go through `lib/api/` and `lib/hooks/` — never inline in components
- [ ] Zod schema validates every API response
- [ ] Forms use React Hook Form + Zod resolver
- [ ] Tests use semantic queries (`getByRole`, `getByText`); `getByTestId` needs justification
- [ ] No mocking `fetch` directly — use MSW
- [ ] No inline styles unless the value is dynamically computed

### ATLAS-specific safety rules (blocking — never skip)

- [ ] **Decision Trace is append-only.** No `UPDATE` or `DELETE` on audit/trace tables or endpoints. Flag and refuse if requested.
- [ ] **Safety-critical flows** (trade execution, framework override, position changes) must have an e2e test covering the typed-confirmation path before they can be considered done.
- [ ] **Regime modifier must be a pure function** — no side effects, no I/O, no randomness.
- [ ] **Conviction scores are read-only intraday** — no code path may recompute or mutate a score outside the post-close batch job.

**Emit at the top of every final code response:**

- `✅ CODE REVIEW PASSED`
- `⚠️ CODE REVIEW — nits noted inline`
- `❌ CODE REVIEW FAILED — [blocking issue]; not presenting code until resolved`

---

## Hard rules that apply to every response

| Rule                       | Detail                                                      |
| -------------------------- | ----------------------------------------------------------- |
| TDD first                  | Failing test before any implementation. No exceptions.      |
| No `any`                   | TypeScript `any` and Python implicit `Any` are both banned. |
| No magic numbers           | Named constants with a comment explaining the value.        |
| No commented-out code      | Delete it.                                                  |
| No bare TODO               | `TODO(#42): …` is fine. Plain `TODO` is not.                |
| Functions do one thing     | Flag anything over 40 lines.                                |
| Decision Trace append-only | Never UPDATE or DELETE from audit/trace tables.             |
| No secrets in code         | Use env vars / config. `.env` is gitignored.                |

---

## Quality gate commands (run mentally before presenting any backend change)

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check .
ruff format --check .
mypy src
pytest --cov=src --cov-fail-under=90

# Frontend
cd frontend
pnpm typecheck
pnpm lint
pnpm format:check
pnpm test:coverage
```

If any gate would fail, fix the issue in your response before presenting the code.

---

## README Maintenance (mandatory — runs alongside every other agent)

### Rule 1 — Every folder has a README.md

Every directory listed below **must** have a `README.md`. If it doesn't exist when you touch that folder, create it before finishing the task.

```
backend/                        ← top-level backend README (setup, quality gate, start command)
backend/src/atlas/api/          ← what the api/ layer does, layering rules
backend/src/atlas/api/v1/       ← full API reference (all endpoints, request/response JSON)
backend/src/atlas/services/     ← what each service does, dependencies
backend/src/atlas/models/       ← ORM models, table names, relationships
backend/src/atlas/schemas/      ← Pydantic schemas, field descriptions
backend/src/atlas/db/           ← session setup, migration workflow
backend/src/atlas/core/         ← logging config, settings
backend/tests/                  ← how to run tests, coverage gate
frontend/                       ← top-level frontend README (setup, start command)
frontend/src/app/               ← routing tree, server vs client components
frontend/src/components/        ← component inventory, design rules
frontend/src/lib/api/           ← every API client function documented
frontend/src/lib/hooks/         ← every hook: purpose, parameters, return shape
frontend/src/lib/schemas/       ← Zod schemas, what they validate
frontend/tests/                 ← test strategy, how to run
```

### Rule 2 — Update the README whenever you change the code

**This is non-negotiable.** Every task that modifies code must also update the corresponding README(s) in the same response. No exceptions.

| Change type                         | README(s) to update                                                       |
| ----------------------------------- | ------------------------------------------------------------------------- |
| New or modified endpoint            | `backend/src/atlas/api/v1/README.md` + `backend/README.md` API table      |
| New or modified service             | `backend/src/atlas/services/README.md`                                    |
| New or modified model               | `backend/src/atlas/models/README.md`                                      |
| New or modified schema              | `backend/src/atlas/schemas/README.md`                                     |
| New or modified API client function | `frontend/src/lib/api/README.md`                                          |
| New or modified hook                | `frontend/src/lib/hooks/README.md`                                        |
| New or modified component           | `frontend/src/components/README.md`                                       |
| Dependency added                    | Both top-level READMEs (backend or frontend)                              |
| Migration added                     | `backend/src/atlas/db/README.md` + `backend/README.md` migrations section |

### Rule 3 — API endpoint documentation format

Every endpoint in `backend/src/atlas/api/v1/README.md` must follow this exact template:

````markdown
### METHOD /api/v1/path

**Description:** One-sentence description of what this endpoint does.
**Auth required:** Yes / No
**Tags:** tag1, tag2

#### Request body (if applicable)

```json
{
  "field": "type — description"
}
```
````

#### Response `200 OK` (or `201 Created`)

```json
{
  "field": "type — description"
}
```

#### Error responses

| Status | When                         |
| ------ | ---------------------------- |
| 404    | Resource not found           |
| 409    | Conflict (duplicate)         |
| 503    | External service unavailable |

```

Use real field names and realistic example values — not just `"string"` or `"number"`.

---

## Tech stack reference

**Backend:** Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2 async · PostgreSQL · Alembic · structlog · pytest · pip + venv · ruff · mypy

**Frontend:** Next.js 16 App Router · TypeScript 5 strict · Tailwind CSS 4 · shadcn/ui · TanStack Query v5 · Zustand · React Hook Form + Zod · Vitest + Testing Library + MSW · Playwright · pnpm
```
