# ATLAS — Setup Prompts & Agents

This bundle contains everything you need to bootstrap the ATLAS project with Claude Code, with strict TDD and clean architecture from day one.

## What's in this bundle

```
.
├── README.md                          ← you are here
├── BACKEND_SETUP.md                   ← prompt to scaffold the FastAPI backend
├── FRONTEND_SETUP.md                  ← prompt to scaffold the Next.js frontend
└── .claude/
    └── agents/
        ├── tdd-enforcer.md            ← blocks impl code without failing tests
        ├── code-reviewer.md           ← runs the quality gate before commits
        └── architecture-guardian.md   ← enforces layering & dependency rules
```

## How to use it

### 1. Create the project root

```bash
mkdir atlas && cd atlas
```

### 2. Copy the agents into place

The `.claude/agents/` directory must live at the **project root** (next to `backend/` and `frontend/`), not inside either subproject. Claude Code automatically picks up agents from there.

```bash
mkdir -p .claude/agents
cp /path/to/this/bundle/.claude/agents/*.md .claude/agents/
```

### 3. Run the backend setup prompt

Open Claude Code in the `atlas/` directory and paste the **entire contents of `BACKEND_SETUP.md`** as your first message. Claude will work through the steps, using the `tdd-enforcer` and `code-reviewer` agents at the appropriate moments.

When it finishes, you'll have a working `backend/` directory with:
- A passing `GET /api/v1/health` endpoint
- ≥90% test coverage
- All quality gates green
- Pre-commit hooks installed

### 4. Run the frontend setup prompt

Once the backend is running, paste the **entire contents of `FRONTEND_SETUP.md`** as your next message in the same Claude Code session (or a new one — agents work either way).

When it finishes, you'll have a working `frontend/` directory with:
- A home page rendering "ATLAS" + live backend health status
- Unit, component, and e2e tests all passing
- Same quality gates and TDD discipline as the backend

### 5. Verify end-to-end

```bash
# Terminal 1 — make sure local Postgres is running, then:
cd backend && uv run uvicorn atlas.main:create_app --factory --reload

# Terminal 2
cd frontend && pnpm dev

# Terminal 3
cd frontend && pnpm test:e2e
```

Visit `http://localhost:3000` and confirm "ATLAS" + "Backend: ok" appears.

## How the agents work together

Once the agents are in `.claude/agents/`, Claude Code will invoke them automatically based on their `description` fields. You can also invoke them manually by name:

- **`tdd-enforcer`** runs at the start of any feature work. It checks that a failing test exists before any implementation gets written. If you try to write code first, it blocks you with `❌ TDD VIOLATION`.

- **`code-reviewer`** runs after implementation is complete, before committing. It runs the full quality gate (lint, types, tests, coverage) and reads the diff for ATLAS-specific rules like Decision Trace immutability and regime modifier purity.

- **`architecture-guardian`** runs when new files, directories, or dependencies are introduced. It enforces the layering rules (`api/` → `services/` → `db/`, never the other way) and the approved dependency list.

The typical loop for any new feature looks like:

1. You ask Claude to add a feature.
2. `tdd-enforcer` makes sure a failing test is written first.
3. `architecture-guardian` confirms the new files go in the right place.
4. Claude writes the minimum implementation.
5. `code-reviewer` runs the quality gate and either approves or sends it back.
6. Commit.

## Project context (the short version)

ATLAS is a decision-support tool for active investing. It computes a daily 0–100 conviction score for each holding using five weighted factors plus a regime modifier (Crisis Halt / Caution / Clear) driven by VIX, Brent crude, and an escalation probability gauge. The UI has three main screens — Daily Briefing, Portfolio, Frameworks — and safety-critical confirmation modals for any trade action. Every confirmed action writes to an append-only Decision Trace log.

The Hello World scaffold doesn't build any of that yet. It builds the foundation those features will sit on, with the discipline they require.

## Tech stack reference

**Backend:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · PostgreSQL 16 · Alembic · pytest · uv · ruff · mypy

**Frontend:** Next.js 15 · React 19 · TypeScript (strict) · TailwindCSS · shadcn/ui · TanStack Query · Zod · React Hook Form · Vitest · React Testing Library · MSW · Playwright · pnpm

## Notes

- The agents assume a monorepo layout with `backend/` and `frontend/` as siblings under `atlas/`. If you split them into separate repos, copy `.claude/agents/` into each repo root.
- The 90% coverage threshold is enforced by the test runners themselves, not just the reviewer agent. You can't accidentally drop below it.
- The TDD enforcer is strict by design. If it feels annoying, that's the point — it's catching the exact mistake that turns disciplined codebases into messes six months in.
