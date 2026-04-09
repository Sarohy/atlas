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

  // ── Ticker search ─────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/tickers/search`, () => {
    return HttpResponse.json([
      { ticker: 'AAPL', name: 'Apple Inc.', market: 'stocks', type: 'CS' },
      { ticker: 'AAPLX', name: 'Apple Something', market: 'stocks', type: 'CS' },
    ]);
  }),

  // ── Portfolio ─────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/portfolio/summary`, () => {
    return HttpResponse.json({
      total_nav: 23900000,
      invested_value: 20315000,
      invested_pct: 85.0,
      cash_balance: 3585000,
      cash_pct: 15.0,
      cash_floor: 2390000,
      cash_floor_pct: 10.0,
      deployable: 1195000,
      day_change: -420000,
      beta_total: 1.09,
      beta_invested: 1.4,
    });
  }),

  http.get(`${BASE}/api/v1/portfolio/cash`, () => {
    return HttpResponse.json({
      cash_balance: 3585000,
      cash_floor_pct: 0.1,
    });
  }),

  http.put(`${BASE}/api/v1/portfolio/cash`, () => {
    return HttpResponse.json({
      cash_balance: 3585000,
      cash_floor_pct: 0.1,
    });
  }),

  http.post(`${BASE}/api/v1/portfolio/cash/adjust`, () => {
    return HttpResponse.json({
      cash_balance: 3985000,
      cash_floor_pct: 0.1,
    });
  }),

  // ── Clusters ──────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/clusters`, () => {
    return HttpResponse.json([
      {
        id: 1,
        name: 'AI Core',
        color: '#4a90d9',
        tickers: [
          {
            id: 1,
            ticker: 'AAPL',
            company_name: 'Apple Inc.',
            shares: '100',
            cluster_id: 1,
            created_at: '2026-04-07T00:00:00Z',
            updated_at: '2026-04-07T00:00:00Z',
          },
        ],
        created_at: '2026-04-07T00:00:00Z',
        updated_at: '2026-04-07T00:00:00Z',
      },
    ]);
  }),

  http.post(`${BASE}/api/v1/clusters`, () => {
    return HttpResponse.json(
      {
        id: 2,
        name: 'Energy',
        color: '#4ade80',
        tickers: [],
        created_at: '2026-04-07T00:00:00Z',
        updated_at: '2026-04-07T00:00:00Z',
      },
      { status: 201 },
    );
  }),

  http.patch(`${BASE}/api/v1/clusters/:id`, () => {
    return HttpResponse.json({
      id: 1,
      name: 'AI Core Updated',
      color: '#38bdf8',
      tickers: [],
      created_at: '2026-04-07T00:00:00Z',
      updated_at: '2026-04-07T00:00:00Z',
    });
  }),

  http.delete(`${BASE}/api/v1/clusters/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Auth ──────────────────────────────────────────────────────────────────────
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

  // ── Momentum ──────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/momentum/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      sector_etf: 'XLK',
      rsi: { value: 62.5, raw_score: 70, score: 14, max_score: 20 },
      macd: {
        macd_line: 1.23,
        signal_line: 0.98,
        histogram: 0.25,
        raw_score: 100,
        score: 15,
        max_score: 15,
      },
      ma_alignment: {
        ma_20: 175.0,
        ma_50: 170.0,
        ma_200: 160.0,
        label: 'ABOVE_ALL',
        raw_score: 100,
        score: 20,
        max_score: 20,
      },
      week_52_position: {
        high_52w: 200.0,
        low_52w: 140.0,
        position_pct: 75.0,
        raw_score: 80,
        score: 12,
        max_score: 15,
      },
      performance: {
        perf_1m: 7.5,
        perf_6m: 22.0,
        raw_score_1m: 85,
        raw_score_6m: 70,
        score_1m: 13,
        score_6m: 7,
        score: 20,
        max_score: 25,
      },
      sector_momentum: {
        sector_etf: 'XLK',
        ticker_perf_6m: 12.0,
        sector_perf_6m: 6.0,
        relative_perf_6m: 6.0,
        raw_score: 100,
        score: 5,
        max_score: 5,
      },
      f1_score: 86,
      f1_grade: 'STRONG BUY',
    });
  }),

  // ── Earnings ──────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/earnings/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      revenue_growth: {
        yoy_pct: 65.0,
        raw_score: 90,
        score: 27,
        max_score: 30,
      },
      eps_beats: {
        beats_in_3: 3,
        quarters_checked: 3,
        raw_score: 100,
        score: 20,
        max_score: 20,
      },
      guidance: {
        guidance_label: 'RAISE_FULL_YEAR',
        transcript_quarter: '2024Q3',
        raw_score: 100,
        score: 20,
        max_score: 20,
      },
      margin_trajectory: {
        gross_margins: [43.0, 44.0, 45.0],
        margin_change_pts: 2.0,
        raw_score: 80,
        score: 12,
        max_score: 15,
      },
      backlog_btb: {
        backlog_label: 'EXPLICIT_MULTI_QUARTER',
        raw_score: 100,
        score: 15,
        max_score: 15,
      },
      f2_score: 94,
      f2_grade: 'STRONG BUY',
    });
  }),

  http.get(`${BASE}/api/v1/analyst/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      consensus_rating: {
        buy_count: 28,
        hold_count: 8,
        sell_count: 2,
        total_analysts: 38,
        buy_pct: 73.7,
        label: 'STRONG BUY',
        score: 20,
        max_score: 20,
      },
      pt_upside: {
        current_price: 182.5,
        consensus_pt: 230.0,
        upside_pct: 26.0,
        score: 20,
        max_score: 20,
      },
      pt_direction: {
        current_consensus_pt: 230.0,
        prior_consensus_pt: 210.0,
        direction_pct: 9.5,
        score: 20,
        max_score: 20,
      },
      analyst_coverage: {
        num_analysts: 38,
        score: 20,
        max_score: 20,
      },
      recent_upgrades: {
        upgrades: 5,
        downgrades: 1,
        net_upgrades: 4,
        score: 20,
        max_score: 20,
      },
      f3_score: 100,
      f3_grade: 'STRONG BUY',
    });
  }),
];
