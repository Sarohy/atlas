# tests/ — Frontend Test Suite

Vitest + Testing Library + MSW. Coverage gate: **≥ 90%** (enforced by `vitest.config.ts`).

## Structure

```
tests/
├── setup.ts              — global test setup (MSW server start/stop, Testing Library config)
├── mocks/
│   └── handlers.ts       — MSW request handlers (mock backend API responses)
├── unit/
│   └── lib/
│       ├── api/          — API client function tests
│       ├── hooks/        — TanStack Query hook tests (use renderHook + MSW)
│       └── schemas/      — Zod schema parse/validation tests
└── components/
    ├── health-status.test.tsx
    ├── home-portfolio-page.test.tsx
    ├── daily-briefing-page.test.tsx
    └── frameworks-page.test.tsx
```

## Running tests

```bash
pnpm test                 # watch mode
pnpm test:coverage        # single run + coverage report (≥90% required)
pnpm test tests/components/health-status.test.tsx  # single file
```

## E2E tests

```bash
# Requires backend on :8000 — Playwright auto-starts pnpm dev on :3000
pnpm test:e2e
pnpm test:e2e --headed    # visible browser
```

E2E tests live in `e2e/`. See `playwright.config.ts` for browser/base URL config.

## Key conventions

- **Component tests**: render with `render()`, query with semantic selectors (`getByRole`, `getByText`). `getByTestId` requires justification.
- **Hook tests**: use `renderHook()` from `@testing-library/react` with a `QueryClient` wrapper.
- **API mock**: all HTTP is intercepted by MSW (`tests/mocks/handlers.ts`) — never mock `fetch` directly.
- **No snapshots**: snapshot tests are brittle and banned. Assert on behavior and visible text.
