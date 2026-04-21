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
        position_value: 100000,
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
        guidance_label: 'NO_DATA_AVAILABLE',
        transcript_quarter: null,
        raw_score: 50,
        score: 10,
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
      f2_score: 84,
      f2_grade: 'STRONG BUY',
    });
  }),

  http.get(`${BASE}/api/v1/analyst/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      consensus_rating: {
        strong_buy_count: 10,
        buy_count: 18,
        hold_count: 8,
        sell_count: 2,
        strong_sell_count: 0,
        total_analysts: 38,
        buy_pct: 73.7,
        label: 'STRONG BUY',
        base_score: 90,
      },
      analyst_coverage: {
        num_analysts: 38,
        modifier: 8,
      },
      pt_direction: {
        raises_30d: 3,
        lowers_30d: 0,
        direction_label: 'MULTIPLE_RAISES',
        modifier: 5,
      },
      recent_upgrades: {
        upgrades_30d: 5,
        downgrades_30d: 1,
        net_upgrades_30d: 4,
        modifier: 5,
      },
      pt_upside: {
        current_price: 182.5,
        consensus_pt: 230.0,
        upside_pct: 26.0,
        price_vs_target: -0.2065,
        price_vs_target_band: '20%+ below target (+10)',
        adjustment: 10,
      },
      f3_before_price_adjustment: 108,
      override_applied: false,
      override_reason: null,
      f3_score: 100,
      f3_grade: 'STRONG BUY',
    });
  }),

  // ── Options Flow ───────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/options-flow/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      whale_block: {
        largest_premium: 1500000,
        score: 80,
        weight: 0.35,
      },
      call_put_ratio: {
        call_premium: 2400000,
        put_premium: 800000,
        ratio: 3,
        score: 75,
        weight: 0.2,
      },
      volume_oi: {
        call_volume: 120000,
        call_open_interest: 60000,
        vol_oi_ratio: 2,
        score: 70,
        weight: 0.2,
      },
      dark_pool: {
        total_dark_pool_premium: 950000,
        largest_print: 300000,
        print_count: 4,
        score: 72,
        weight: 0.15,
      },
      sweep_type: {
        has_golden_sweep: false,
        has_single_sweep: true,
        has_repeated_hits: true,
        sweep_premium: 250000,
        score: 68,
        weight: 0.1,
      },
      signal_tier: 'BLUE',
      collar_flag: false,
      f4_score: 74,
      f4_grade: 'BUY',
    });
  }),

  // ── Fundamental ────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/fundamental/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      insider_activity: {
        net_buy_value: 500000,
        net_sell_value: 0,
        transaction_count: 2,
        c_suite_sell_value: 0,
        ceo_cfo_sell_value: 0,
        activity_label: 'NET_BUYING',
        score: 85,
        weight: 0.3,
      },
      altman_z: {
        z_score: 3.1,
        x1_working_capital_ratio: 0.2,
        x2_retained_earnings_ratio: 0.3,
        x3_ebit_ratio: 0.18,
        x4_market_cap_to_liabilities: 2.6,
        x5_revenue_to_assets: 1.1,
        zone: 'SAFE',
        score: 80,
        weight: 0.25,
      },
      free_cash_flow: {
        fcf_current: 2200000000,
        fcf_prior: 1800000000,
        fcf_trend: 'POSITIVE_GROWING',
        score: 78,
        weight: 0.2,
      },
      debt_equity: {
        total_debt: 1000000000,
        total_equity: 5000000000,
        ratio: 0.2,
        score: 75,
        weight: 0.15,
      },
      institutional_ownership: {
        ownership_pct: 0.72,
        change_label: 'NET_BUYING',
        score: 70,
        weight: 0.1,
      },
      insider_cap: null,
      altman_cap: null,
      f5_blocked: false,
      active_cap: null,
      f5_score: 77,
      f5_grade: 'GOOD',
      data_available: true,
    });
  }),

  // ── Market Conditions ─────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/market/conditions`, () => {
    return HttpResponse.json({
      brent_price: 97.5,
      brent_prev_price: 96.8,
      vix_value: 27.3,
    });
  }),

  // ── Regime Modifier ──────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/regime-modifier/:ticker`, ({ params, request }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    const url = new URL(request.url);
    const geopoliticalState = (url.searchParams.get('geopolitical_state') ?? 'ACTIVE').toUpperCase();
    const ruleTriggered = 2;
    const baseScore = 79;
    return HttpResponse.json({
      ticker,
      geopolitical_state: geopoliticalState,
      brent_price: 97.5,
      vix_value: 27.3,
      brent_consecutive_below_95_count: 2,
      base_score: baseScore,
      adjusted_score: baseScore - 5,
      rule_triggered: ruleTriggered,
      rule: 'CAUTION',
      effective_regime: geopoliticalState === 'NONE' ? 'CAUTION' : 'SOFT CAUTION',
      min_cash_pct: 0.25,
      max_cash_pct: 0.35,
      min_cash_usd: 25000,
      max_cash_usd: 35000,
      output_text: 'must stay in cash',
      determination_text:
        geopoliticalState === 'NONE'
          ? 'Automatic regime CAUTION from Brent/VIX data. Brent streak below $95: 2. No geopolitical gate applied.'
          : 'Automatic regime CAUTION from Brent/VIX data. Brent streak below $95: 2. Geopolitical flag ACTIVE adds a secondary gate, so the displayed regime is SOFT CAUTION.',
    });
  }),

  // ── Position Sizing ─────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/position-sizing/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      conviction_score: 79,
      tier: 'TIER_2',
      action: 'GTC ADDS PERMITTED',
      grey_zone: false,
      consensus_required: false,
      trigger_exit_rules: false,
      adds_permitted: true,
      leaps_eligible: false,
      display_message: 'GTC adds permitted.',
      consensus_confirmed: false,
    });
  }),

  // ── Tranche Sizing ───────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/tranche-sizing/:ticker`, ({ params, request }) => {
    const rawTicker = String(params['ticker'] ?? 'AAPL');
    const ticker = rawTicker.toUpperCase();
    const url = new URL(request.url);
    const initialCatalyst = url.searchParams.get('initial_catalyst') ?? 'no';
    const regimeRule = (url.searchParams.get('regime_rule') ?? 'NORMAL').toUpperCase();
    const iranResolution = url.searchParams.get('iran_resolution');
    const positionWeightOverride = url.searchParams.get('position_weight_override');
    const signalsCountOverride = url.searchParams.get('signals_count_override');

    // Determine position weight: override > known caps > default 0
    const CAP_WEIGHTS: Record<string, number> = { MU: 0.136, TSM: 0.117, COHR: 0.095 };
    const positionWeight =
      positionWeightOverride !== null
        ? parseFloat(positionWeightOverride)
        : (CAP_WEIGHTS[ticker] ?? 0.0);

    const capActive = positionWeight >= 0.08;

    if (capActive) {
      const emptySignals = Array.from({ length: 5 }, (_, i) => ({
        signal_index: i + 1,
        name: `Signal ${i + 1}`,
        confirmed: false,
      }));
      return HttpResponse.json({
        ticker,
        cap_active: true,
        tranche_display: false,
        position_weight: positionWeight,
        message: 'Adds blocked by concentration cap - tranche sizing N/A',
        and_gate_active: false,
        and_gate_passed: false,
        signals_confirmed: 0,
        signals_detail: emptySignals,
        t1_fired: false,
        t1: null,
        t2: null,
        t3: null,
        t4: null,
      });
    }

    // Determine AND gate
    const andGateActive = regimeRule === 'CLEAR';
    const signalsCount =
      signalsCountOverride !== null ? parseInt(signalsCountOverride, 10) : 0;
    const andGatePassed = andGateActive && signalsCount >= 3;
    const signals = Array.from({ length: 5 }, (_, i) => ({
      signal_index: i + 1,
      name: `Signal ${i + 1}`,
      confirmed: i < signalsCount,
    }));

    // Sequential gate: T2/T3/T4 blocked until T1 fires.
    const t1Fired = initialCatalyst === 'yes';

    return HttpResponse.json({
      ticker,
      cap_active: false,
      tranche_display: true,
      position_weight: positionWeight,
      message: null,
      and_gate_active: andGateActive,
      and_gate_passed: andGatePassed,
      signals_confirmed: andGateActive ? signalsCount : 0,
      signals_detail: signals,
      t1_fired: t1Fired,
      t1: t1Fired ? '10-15% of available cash' : 'Blocked',
      t2: t1Fired && regimeRule === 'CAUTION' ? '20-25% of available cash' : 'Blocked',
      t3: t1Fired && andGatePassed ? '30-40% of available cash' : 'Blocked',
      t4:
        t1Fired && iranResolution === 'confirmed' ? 'Remaining cash to floor' : 'Blocked',
    });
  }),

  // ── Framework Score ───────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/framework-score/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'AAPL');
    return HttpResponse.json({
      ticker,
      factors: [
        {
          key: 'f1',
          name: 'Momentum',
          score: 86,
          weight: 0.2,
          contribution: 17.2,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f2',
          name: 'Earnings Quality',
          score: 94,
          weight: 0.25,
          contribution: 23.5,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f3',
          name: 'Analyst Sentiment',
          score: 100,
          weight: 0.15,
          contribution: 15.0,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f4',
          name: 'Options Flow',
          score: 82,
          weight: 0.15,
          contribution: 12.3,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f5',
          name: 'Fundamental Quality',
          score: 78,
          weight: 0.2,
          contribution: 15.6,
          grade: 'BUY',
          available: true,
        },
      ],
      raw_total: 83.6,
      final_score: 79,
      action: 'HOLD',
      action_tone: 'tone-yellow',
      f5_blocked: false,
      flags: [],
    });
  }),

  // ── Framework 14 — Position Sizing Rules ─────────────────────────────────
  http.get(`${BASE}/api/v1/framework14/:ticker`, ({ params }) => {
    const ticker = String(params['ticker']).toUpperCase();
    return HttpResponse.json({
      ticker,
      position_weight_pct: 13.6,
      nav_dollars: 23900000,
      position_dollars: 3250400,
      sizing_tier: 'CORE_ANCHOR',
      target_weight_min: 0.03,
      target_weight_max: 0.05,
      concentration_status: 'GRANDFATHERED',
      cap_active: true,
      soft_cap_breached: true,
      hard_review_triggered: true,
      grandfathered: true,
      grandfathered_expires_at: 0.17,
      grandfathered_expiry_near: false,
      score_display_cap: 85,
      cluster: 'AI Memory',
      cluster_weight_pct: 25.3,
      cluster_status: 'RED_ZONE',
      cluster_yellow_threshold: 0.22,
      cluster_red_threshold: 0.25,
      adds_permitted: false,
      trim_recommended: true,
      message:
        `${ticker} is grandfathered above the 8% soft cap. No new adds. Monitor expiry threshold.`,
    });
  }),
];
