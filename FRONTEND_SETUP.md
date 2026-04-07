# ATLAS Frontend — Hello World Setup Prompt

You are setting up the frontend for **ATLAS**, a decision-support tool for active investing. This is the initial scaffold — a Hello World page that fetches from the backend health endpoint — but it must follow production best practices and **strict test-driven development (TDD)** from commit one.

Do not skip steps. Do not write component code before tests. After each step, run the tests and confirm they pass before moving on.

---

## Project Context

ATLAS will eventually have three main screens — Daily Briefing, Portfolio, and Frameworks — plus a persistent top bar showing VIX, Brent crude, and the 10-year Treasury yield, and safety-critical confirmation modals for trade execution. None of that exists yet. Right now we are scaffolding the foundation with one working page: `/` displays "ATLAS" and live status from the backend `/api/v1/health` endpoint.

The structure must support what is coming next: dashboard layouts, data fetching with caching, form validation for typed confirmations, and chart rendering.

---

## Tech Stack (non-negotiable)

- **Next.js 15+** with App Router
- **React 19**
- **TypeScript** in strict mode
- **TailwindCSS** for styling
- **shadcn/ui** for component primitives
- **TanStack Query v5** for server state
- **Zustand** for client state (not needed yet, install but don't use)
- **React Hook Form + Zod** for form validation (install but don't use yet)
- **Vitest** + **React Testing Library** + **MSW** for unit/component tests
- **Playwright** for end-to-end tests
- **ESLint + Prettier** for linting and formatting
- **pnpm** as the package manager
- **Husky + lint-staged** for pre-commit hooks

---

## Required Project Structure

Create exactly this layout:

```
frontend/
├── .env.example
├── .env.local                  # gitignored
├── .eslintrc.json
├── .gitignore
├── .prettierrc
├── .husky/
│   └── pre-commit
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── vitest.config.ts
├── playwright.config.ts
├── components.json             # shadcn/ui config
├── package.json
├── README.md
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # home — shows ATLAS + health status
│   │   ├── providers.tsx       # QueryClientProvider wrapper
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                 # shadcn primitives go here
│   │   └── health-status.tsx   # client component fetching health
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts       # fetch wrapper with base URL + error handling
│   │   │   └── health.ts       # typed health API call
│   │   ├── schemas/
│   │   │   └── health.ts       # Zod schema mirroring backend
│   │   ├── hooks/
│   │   │   └── use-health.ts   # TanStack Query hook
│   │   └── utils.ts            # cn() helper from shadcn
│   └── types/
│       └── api.ts              # shared API types
├── tests/
│   ├── setup.ts                # Vitest setup
│   ├── mocks/
│   │   ├── handlers.ts         # MSW request handlers
│   │   └── server.ts           # MSW node server
│   ├── unit/
│   │   ├── schemas/
│   │   │   └── health.test.ts
│   │   └── lib/
│   │       └── api-client.test.ts
│   └── components/
│       └── health-status.test.tsx
└── e2e/
    ├── home.spec.ts
    └── fixtures.ts
```

---

## Step-by-Step Instructions

### Step 1 — Initialize the project

1. Run `pnpm create next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm`. Decline Turbopack for now (Vitest plays nicer with Webpack).
2. `cd frontend`
3. Install runtime dependencies:
   ```
   pnpm add @tanstack/react-query zustand react-hook-form @hookform/resolvers zod
   ```
4. Install dev dependencies:
   ```
   pnpm add -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw @playwright/test prettier eslint-config-prettier eslint-plugin-testing-library husky lint-staged
   ```
5. Initialize shadcn/ui: `pnpm dlx shadcn@latest init` (choose New York style, slate base color, CSS variables yes).
6. Add the Card primitive: `pnpm dlx shadcn@latest add card`.
7. Create the directory structure shown above.

### Step 2 — Configure tooling

1. **`tsconfig.json`** — ensure `"strict": true`, add `"noUncheckedIndexedAccess": true` and `"noImplicitOverride": true`.
2. **`.eslintrc.json`** — extend `next/core-web-vitals`, `next/typescript`, `prettier`, and `plugin:testing-library/react`. Add rule `"@typescript-eslint/no-unused-vars": "error"`.
3. **`.prettierrc`** — `{ "semi": true, "singleQuote": true, "trailingComma": "all", "printWidth": 100, "tabWidth": 2 }`.
4. **`vitest.config.ts`** — configure jsdom environment, setup file at `tests/setup.ts`, path alias `@/` matching tsconfig, coverage thresholds 90% lines/functions/branches.
5. **`tests/setup.ts`** — import `@testing-library/jest-dom`, start MSW server before all tests, reset handlers after each, close after all.
6. **`playwright.config.ts`** — base URL `http://localhost:3000`, run `pnpm dev` as web server, Chromium only for now.
7. **`package.json` scripts**:
   ```json
   {
     "scripts": {
       "dev": "next dev",
       "build": "next build",
       "start": "next start",
       "lint": "next lint",
       "format": "prettier --write .",
       "format:check": "prettier --check .",
       "typecheck": "tsc --noEmit",
       "test": "vitest run",
       "test:watch": "vitest",
       "test:coverage": "vitest run --coverage",
       "test:e2e": "playwright test",
       "prepare": "husky"
     }
   }
   ```
8. **Husky + lint-staged**: `pnpm exec husky init`, then in `.husky/pre-commit` run `pnpm lint-staged`. In `package.json` add:
   ```json
   "lint-staged": {
     "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
     "*.{json,md,css}": ["prettier --write"]
   }
   ```

### Step 3 — Write the failing tests FIRST

This is the TDD step. Do not write component or schema code yet.

**`tests/mocks/handlers.ts`** — define an MSW handler for `GET http://localhost:8000/api/v1/health` returning `{ status: "ok", service: "atlas-backend" }`.

**`tests/mocks/server.ts`** — `setupServer(...handlers)` from `msw/node`.

**`tests/unit/schemas/health.test.ts`** — write tests that:
- Import `healthResponseSchema` from `@/lib/schemas/health`
- Parse a valid payload successfully
- Reject a payload missing `status`
- Reject a payload with wrong types

**`tests/unit/lib/api-client.test.ts`** — write tests that:
- Import `fetchHealth` from `@/lib/api/health`
- Call it and assert it returns the parsed object
- Override the MSW handler to return a 500 and assert `fetchHealth` throws a typed error
- Override the handler to return malformed JSON and assert it throws a validation error

**`tests/components/health-status.test.tsx`** — write tests that:
- Render `<HealthStatus />` wrapped in a `QueryClientProvider`
- Assert a loading state appears initially
- Wait for and assert "Backend: ok" text appears
- Override the handler to return 500 and assert an error state renders

**`e2e/home.spec.ts`** — write a Playwright test that:
- Visits `/`
- Asserts the page heading "ATLAS" is visible
- Asserts the text "Backend: ok" eventually appears (this requires the real backend running, document this in the README)

Run `pnpm test`. **Confirm all unit and component tests fail** with import or module-not-found errors. Skip e2e for now (it needs the backend).

### Step 4 — Implement the minimum code to pass

Now write only enough code to make the tests green:

1. **`src/lib/schemas/health.ts`** — Zod schema:
   ```ts
   import { z } from 'zod';
   export const healthResponseSchema = z.object({
     status: z.string(),
     service: z.string(),
   });
   export type HealthResponse = z.infer<typeof healthResponseSchema>;
   ```
2. **`src/lib/api/client.ts`** — typed fetch wrapper that takes a Zod schema, throws `ApiError` on non-2xx, throws `ApiValidationError` on schema mismatch. Reads base URL from `process.env.NEXT_PUBLIC_API_URL`.
3. **`src/lib/api/health.ts`** — `fetchHealth()` that calls the client with `healthResponseSchema`.
4. **`src/lib/hooks/use-health.ts`** — `useHealth()` TanStack Query hook with key `['health']`, calling `fetchHealth`, refetch interval 30 seconds.
5. **`src/app/providers.tsx`** — client component wrapping children in `QueryClientProvider` with a single `QueryClient` instance.
6. **`src/components/health-status.tsx`** — client component using `useHealth`. Renders loading state, error state, and success state ("Backend: ok").
7. **`src/app/layout.tsx`** — wrap children in `<Providers>`.
8. **`src/app/page.tsx`** — server component rendering an `<h1>ATLAS</h1>` and the `<HealthStatus />` component inside a shadcn `Card`.
9. **`.env.example`** — `NEXT_PUBLIC_API_URL=http://localhost:8000`.
10. **`.env.local`** — same value (gitignored).

Run `pnpm test`. **All unit and component tests must now pass.** Run `pnpm typecheck && pnpm lint && pnpm format:check`. All must pass.

### Step 5 — End-to-end verification

1. Start the backend (separate terminal): see backend README.
2. Start the frontend: `pnpm dev`.
3. Visit `http://localhost:3000`. Confirm "ATLAS" heading and "Backend: ok" text are visible.
4. Run `pnpm test:e2e` and confirm the Playwright test passes.

### Step 6 — Document and commit

1. Write a `README.md` covering: prerequisites, setup commands, how to run tests (unit, component, e2e), how to run the dev server, project structure overview, environment variables, and TDD workflow expectations.
2. Initialize git (or commit into the existing monorepo), make a single commit: `chore: initial frontend scaffold with health status`.

---

## TDD Rules You Must Follow Going Forward

These rules apply to **every future feature**, not just this scaffold:

1. **Red → Green → Refactor.** Write the failing test first. Write the minimum code to pass. Then refactor.
2. **No untested code paths.** Coverage must stay ≥90%. The vitest config enforces this.
3. **Every component needs a component test.** Every API call needs a unit test with MSW. Every Zod schema needs a unit test for both valid and invalid inputs.
4. **Every safety-critical user flow needs an e2e test.** When confirmation modals are added later, every typed-confirmation path gets a Playwright test.
5. **Tests describe user behavior, not implementation.** Use `getByRole`, `getByText`, `findByText`. Avoid `getByTestId` unless there is no semantic alternative.
6. **MSW handlers are the source of truth for API mocks.** Do not mock `fetch` directly in tests.
7. **No `any` types.** No `// eslint-disable` without an attached comment explaining why.

---

## Acceptance Criteria

Before declaring this step done, confirm:

- [ ] `pnpm test` passes with ≥90% coverage
- [ ] `pnpm typecheck` passes in strict mode
- [ ] `pnpm lint` passes
- [ ] `pnpm format:check` passes
- [ ] `pnpm dev` starts cleanly and the home page renders "ATLAS" + "Backend: ok"
- [ ] `pnpm test:e2e` passes (with backend running)
- [ ] Pre-commit hooks installed and blocking bad commits
- [ ] README documents everything above

---

## What NOT to do

- Do not build the Daily Briefing, Portfolio, or Frameworks screens yet — that's later phases.
- Do not skip the failing-test step. If you write components first, delete them and start over.
- Do not lower the coverage threshold.
- Do not commit with failing linters or type checks.
- Do not use `getByTestId` when a semantic query works.
- Do not put fetch calls inside components — always go through `lib/api/` and `lib/hooks/`.
- Do not mock `fetch` directly — use MSW.
