# app/ — Next.js App Router

All pages and layouts. Server Components by default — `'use client'` only when hooks or interactivity are needed.

## Route tree

```
app/
├── layout.tsx          — root layout (fonts, QueryClient provider, auth guard)
├── page.tsx            — root redirect → /(atlas)/portfolio
├── providers.tsx       — client-side React Query + other context providers
├── globals.css         — global Tailwind base
├── auth/
│   └── page.tsx        — /auth — sign-in screen
└── (atlas)/            — route group with shared chrome (sidebar + topbar)
    ├── layout.tsx      — AtlasChrome wrapper
    ├── portfolio/
    │   └── page.tsx    — /portfolio — holdings, tickers, portfolio summary
    ├── daily-briefing/
    │   └── page.tsx    — /daily-briefing — conviction scores, regime status
    ├── frameworks/
    │   └── page.tsx    — /frameworks — risk framework rules
    ├── clusters/
    │   └── page.tsx    — /clusters — position cluster management
    └── watchlist/
        └── page.tsx    — /watchlist — monitored tickers
```

## Rules

- Pages are server components — fetch data at the server level where possible.
- Mark with `'use client'` only if the component uses hooks (`useState`, `useEffect`, `useQuery`, etc.) or browser APIs.
- Never put raw `fetch()` calls in page files — use `lib/api/` functions.
- Layouts wrap pages with shared chrome; never put business logic in layouts.
