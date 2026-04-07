# ATLAS — Frontend

Next.js 16 (App Router) front-end for the ATLAS decision-support tool.

## Prerequisites

| Tool          | Version                                                    |
| ------------- | ---------------------------------------------------------- |
| Node.js       | ≥ 22.0.0                                                   |
| pnpm          | ≥ 10.0.0                                                   |
| ATLAS backend | running on `http://localhost:8000` (required for e2e only) |

> **Tip:** use `nvm` to manage Node versions.  
> `nvm install 22 && nvm use 22`

---

## Setup

```bash
# 1. Install dependencies
pnpm install

# 2. Copy environment file
cp .env.example .env.local
# Edit .env.local if the backend runs on a different host/port
```

### Environment variables

| Variable              | Default                 | Description                       |
| --------------------- | ----------------------- | --------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the ATLAS backend API |

---

## Development server

```bash
pnpm dev        # starts on http://localhost:3000
```

---

## Testing

### Unit / component tests (Vitest + Testing Library)

```bash
pnpm test              # run all unit tests (watch mode)
pnpm test:coverage     # single run with coverage report (≥ 90% thresholds)
```

Tests live in `tests/` and use **MSW** to mock the backend — no running backend required.

### End-to-end tests (Playwright)

```bash
# Requires the backend to be running on :8000 first:
# cd ../backend && uv run uvicorn atlas.main:create_app --factory --port 8000

pnpm test:e2e          # Playwright auto-starts `pnpm dev` on :3000, then runs Chromium tests
```

E2E tests live in `e2e/`.

---

## Quality gate

```bash
pnpm typecheck     # tsc --noEmit
pnpm lint          # ESLint (src + tests)
pnpm format        # Prettier write
pnpm format:check  # Prettier check (CI)
```

All four commands must pass before committing — enforced by Husky + lint-staged on `git commit`.

---

## Project structure

```
src/
├── app/
│   ├── layout.tsx          # Root layout — wraps children in <Providers>
│   ├── page.tsx            # Home page — renders <HealthStatus> inside a Card
│   └── providers.tsx       # TanStack Query QueryClientProvider
├── components/
│   ├── health-status.tsx   # Client component: polls /api/v1/health every 30 s
│   └── ui/
│       └── card.tsx        # shadcn/ui Card (manually created)
├── lib/
│   ├── api/
│   │   ├── client.ts       # apiFetch() — typed fetch wrapper with Zod validation
│   │   └── health.ts       # fetchHealth() — calls GET /api/v1/health
│   ├── hooks/
│   │   └── use-health.ts   # useHealth() TanStack Query hook
│   ├── schemas/
│   │   └── health.ts       # Zod HealthResponse schema
│   └── utils.ts            # cn() — clsx + tailwind-merge helper
└── types/
    └── api.ts              # Shared API response types

tests/
├── mocks/
│   ├── handlers.ts         # MSW request handlers
│   └── server.ts           # MSW node server (used by Vitest)
├── setup.ts                # jest-dom matchers + MSW lifecycle hooks
├── unit/                   # Pure unit tests (schemas, API client)
└── components/             # Component render tests

e2e/
├── fixtures.ts             # Playwright base test (extendable)
└── home.spec.ts            # Home page smoke test
```

---

## TDD workflow

1. **Red** — write a failing test in `tests/` (or `e2e/`)
2. **Green** — write the minimum code to make it pass
3. **Refactor** — clean up, keeping tests green
4. Run `pnpm test:coverage` to verify ≥ 90% coverage
5. Run `pnpm typecheck && pnpm lint && pnpm format:check` before committing

---

## Tech stack

| Concern       | Library                              |
| ------------- | ------------------------------------ |
| Framework     | Next.js 16 (App Router)              |
| Language      | TypeScript 5 (strict)                |
| Styling       | Tailwind CSS 4                       |
| UI primitives | shadcn/ui (manual) + Radix UI        |
| Server state  | TanStack Query v5                    |
| Client state  | Zustand                              |
| Forms         | React Hook Form + Hookform Resolvers |
| Validation    | Zod v4                               |
| Unit tests    | Vitest + Testing Library + MSW       |
| E2E tests     | Playwright                           |
| Linting       | ESLint (flat config) + Prettier      |
| Git hooks     | Husky + lint-staged                  |
