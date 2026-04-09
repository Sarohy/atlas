# components/ — React Components

Reusable UI components. May import from `lib/`. Must never make raw `fetch()` calls.

## Structure

```
components/
├── health-status.tsx       — live backend health indicator (used in layout)
├── atlas/
│   └── atlas-chrome.tsx    — main app shell: sidebar navigation + topbar
├── auth/
│   └── sign-in-form.tsx    — email/password form with React Hook Form + Zod
├── clusters/
│   ├── clusters-screen.tsx — full clusters management page component
│   └── ...
├── daily-briefing/
│   └── daily-briefing-screen.tsx
├── frameworks/
│   └── frameworks-screen.tsx
├── portfolio/
│   ├── portfolio-screen.tsx          — page-level composition
│   ├── portfolio-summary-panel.tsx   — NAV, cash, beta rail
│   ├── portfolio-tickers-panel.tsx   — ticker list, add/edit dialogs
│   └── ticker-search.tsx             — autocomplete search via Polygon
└── watchlist/
    └── watchlist-screen.tsx
```

## Rules

- Components receive data via props or TanStack Query hooks — never inline `fetch`.
- All API interaction goes through `lib/hooks/` → `lib/api/`.
- Server components by default. Add `'use client'` only when needed.
- One component per file. File name matches the exported component name (kebab-case).
- Styling: Tailwind utility classes + `src/styles/*.css` for component-specific rules.
- No inline styles unless the value is dynamically computed (e.g. a hex color from data).
