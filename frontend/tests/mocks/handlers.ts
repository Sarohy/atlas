import { delay, http, HttpResponse } from 'msw';

const BASE = 'http://localhost:8000';

export const handlers = [
  // ── Health ──────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/health`, () => {
    return HttpResponse.json({ status: 'ok', service: 'atlas-backend' });
  }),

  // ── Tickers ────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/tickers`, () => {
    return HttpResponse.json([
      {
        id: 1,
        ticker: 'AAPL',
        company_name: 'Apple Inc.',
        shares: '100',
        created_at: '2026-04-07T00:00:00Z',
        updated_at: '2026-04-07T00:00:00Z',
      },
    ]);
  }),

  http.post(`${BASE}/api/v1/tickers`, () => {
    return HttpResponse.json(
      {
        id: 2,
        ticker: 'NVDA',
        company_name: 'NVIDIA Corporation',
        shares: '25',
        created_at: '2026-04-07T00:00:00Z',
        updated_at: '2026-04-07T00:00:00Z',
      },
      { status: 201 },
    );
  }),

  http.patch(`${BASE}/api/v1/tickers/:id`, () => {
    return HttpResponse.json({
      id: 1,
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      shares: '200',
      created_at: '2026-04-07T00:00:00Z',
      updated_at: '2026-04-07T00:00:00Z',
    });
  }),

  http.delete(`${BASE}/api/v1/tickers/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Ticker search ─────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/tickers/search`, () => {
    return HttpResponse.json([
      { ticker: 'AAPL', name: 'Apple Inc.', market: 'stocks', type: 'CS' },
      { ticker: 'AAPLX', name: 'Apple Something', market: 'stocks', type: 'CS' },
    ]);
  }),

  http.post('http://localhost:8000/api/v1/auth/sign-in', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    await delay(150);

    if (body.email === 'admin@atlas.com' && body.password === 'admin@123') {
      return HttpResponse.json({
        email: 'admin@atlas.com',
        message: 'Sign in successful.',
      });
    }

    return HttpResponse.json({ detail: 'Invalid email or password.' }, { status: 401 });
  }),
  http.post('http://localhost:8000/api/v1/auth/logout', async () => {
    await delay(100);

    return HttpResponse.json({
      message: 'Logout successful.',
    });
  }),
];
