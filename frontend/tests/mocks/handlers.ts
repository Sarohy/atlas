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
  // ── Live beta ────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/tickers/beta/live`, () => {
    return HttpResponse.json({ AAPL: 1.23 });
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
      sf1_revenue_growth_pct: 65.0,
      sf1_score: 90,
      sf2_gross_margin_trend_bps: 120,
      sf2_score: 80,
      sf3_eps_beats: 4,
      sf3_quarters_available: 4,
      sf3_score: 100,
      sf3_excluded: false,
      sf4_guidance_delivered: null,
      sf4_score: 10,
      sf4_data_gap: true,
      sf5_forward_visibility_label: 'SPECIFIC_RAISED',
      sf5_score: 100,
      f2_raw: 87.5,
      f2_contribution: 21.875,
      f2_score: 88,
      f2_grade: 'STRONG BUY',
      pre_profit_status: false,
      pre_profit_reweighted: false,
      data_gap_applied: true,
      guidance_concern: false,
      exit_flag: false,
      limited_history: false,
      ipo_limited_history: false,
      data_available: true,
      is_pre_profitability: false,
      breakdown: {},
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
      f4_score: 74,
      f4_grade: 'BUY',
      dark_pool_score: 72,
      options_flow_score: 76,
      dark_pool_net_flow_usd: 12_500_000,
      options_net_flow_usd: 4_300_000,
      market_cap_usd: 75_000_000_000,
      market_cap_tier: 'LARGE',
      flow_direction: 'BULLISH',
      data_source: 'BOTH',
      data_gap_reason: null,
      lookback_sessions: 5,
      dark_pool_prints_count: 18,
      dark_pool_large_buy_count: 3,
      largest_dark_pool_buy_usd: 2_500_000,
      largest_options_buy_usd: 850_000,
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
    const geopoliticalState = (
      url.searchParams.get('geopolitical_state') ?? 'ACTIVE_RISK'
    ).toUpperCase();
    const ruleTriggered = 2;
    const baseScore = 79;
    const specialCaseActive = geopoliticalState === 'ESCALATING';
    const modifier = specialCaseActive ? -7 : -5;
    return HttpResponse.json({
      ticker,
      geopolitical_state: geopoliticalState,
      brent_price: 97.5,
      vix_value: 27.3,
      brent_consecutive_below_95_count: 2,
      base_score: baseScore,
      adjusted_score: baseScore + modifier,
      rule_triggered: ruleTriggered,
      rule: 'CAUTION',
      effective_regime: 'CAUTION',
      modifier,
      min_cash_pct: 0.25,
      max_cash_pct: 0.35,
      min_cash_usd: 25000,
      max_cash_usd: 35000,
      output_text: specialCaseActive
        ? 'must stay in cash\nGEO PENALTY ACTIVE: CAUTION + ESCALATING'
        : 'must stay in cash',
      determination_text: `CAUTION regime from Brent/VIX data. Brent streak below $95: 2. Geo flag: ${geopoliticalState}. Modifier: ${modifier}.`,
      brent_condition: '$97.50 — $95-110 (CAUTION trigger)',
      vix_condition: '27.30 — 24-35 (CAUTION trigger)',
      geo_condition: geopoliticalState,
      trigger_logic: 'OR — either Brent or VIX triggers',
      modifier_reason: specialCaseActive
        ? 'CAUTION + Escalating geo → −7'
        : `CAUTION + ${geopoliticalState} → −5`,
      special_case_active: specialCaseActive,
      cash_floor_pct: 0.2,
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
    const brentConsecutive = parseInt(
      url.searchParams.get('brent_consecutive_below_95_count') ?? '0',
      10,
    );
    const geoState = (url.searchParams.get('geopolitical_state') ?? 'NONE').toUpperCase();
    const brentPriceParam = url.searchParams.get('brent_price');
    const brentPrice = brentPriceParam !== null ? parseFloat(brentPriceParam) : null;

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
        t2_fired: false,
        t2_pending: false,
        t3_fired: false,
        t3_pending: false,
        t1: null,
        t2: null,
        t3: null,
        t4: null,
      });
    }

    // Determine AND gate
    const andGateActive = regimeRule === 'CLEAR';
    let signalsCount = signalsCountOverride !== null ? parseInt(signalsCountOverride, 10) : 0;
    if (signalsCountOverride === null) {
      // Auto-detect signal 2 (Brent consecutive) and signal 5 (geo RESOLVED)
      const sig2 = brentConsecutive >= 2 ? 1 : 0;
      const sig5 = geoState === 'RESOLVED' ? 1 : 0;
      signalsCount = sig2 + sig5;
    }
    const andGatePassed = andGateActive && signalsCount >= 3;
    const signals = Array.from({ length: 5 }, (_, i) => ({
      signal_index: i + 1,
      name: `Signal ${i + 1}`,
      confirmed: i < signalsCount,
    }));

    // Sequential gate: T2/T3/T4 blocked until T1 fires.
    const t1Fired = initialCatalyst === 'yes';
    const t2Value =
      t1Fired && brentPrice !== null && brentPrice < 110 ? '20-25% of available cash' : 'Blocked';
    const t3Value = t1Fired && andGatePassed ? '30-40% of available cash' : 'Blocked';
    const t2Conditions = t2Value !== 'Blocked';
    const t3Conditions = t3Value !== 'Blocked';

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
      t2_fired: false,
      t2_pending: t2Conditions,
      t3_fired: false,
      t3_pending: t3Conditions,
      catalyst_confirmed: t1Fired,
      t1: t1Fired ? '10-15% of available cash' : 'Blocked',
      t2: t2Value,
      t3: t3Value,
      t4: t1Fired && iranResolution === 'confirmed' ? 'Remaining cash to floor' : 'Blocked',
    });
  }),

  // ── Tranche sizing confirm T2 ─────────────────────────────────────────────
  http.post(`${BASE}/api/v1/tranche-sizing/:ticker/confirm-t2`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Tranche sizing confirm T3 ─────────────────────────────────────────────
  http.post(`${BASE}/api/v1/tranche-sizing/:ticker/confirm-t3`, () => {
    return new HttpResponse(null, { status: 204 });
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
      message: `${ticker} is grandfathered above the 8% soft cap. No new adds. Monitor expiry threshold.`,
    });
  }),

  // ── Framework 13 — Beta-Adjusted Portfolio Management ────────────────────
  http.get(`${BASE}/api/v1/framework13/portfolio/beta`, () => {
    return HttpResponse.json({
      weighted_avg_beta: 1.82,
      effective_beta: 1.62,
      cash_percentage: 0.11,
      target_beta: 1.75,
      beta_status: 'NORMAL',
      warning_level: 'NONE',
      warning_message: null,
      position_betas: [
        { ticker: 'AAOI', weight: 0.005, beta: 4.03, contribution: 0.02015, source: 'CONFIRMED' },
        { ticker: 'MU', weight: 0.03, beta: 1.65, contribution: 0.0495, source: 'CONFIRMED' },
      ],
    });
  }),

  http.get(`${BASE}/api/v1/framework13/:ticker`, ({ params, request }) => {
    const ticker = String(params['ticker'] ?? '').toUpperCase();
    const url = new URL(request.url);
    const positionWeight = parseFloat(url.searchParams.get('position_weight_override') ?? '0.01');

    // Hardcoded confirmed beta table — mirrors backend service
    const CONFIRMED_BETAS: Record<string, number> = {
      AAOI: 4.03,
      CRDO: 2.67,
      UCTT: 2.0,
      MRVL: 1.98,
      VICR: 1.95,
      TTMI: 1.95,
      NBIS: 1.9,
      SNDK: 1.85,
      LITE: 1.8,
      COHR: 1.75,
      AEHR: 1.75,
      MU: 1.65,
      CIEN: 1.55,
      TSM: 1.3,
      FN: 2.7,
      TSEM: 0.82,
      NEM: 0.55,
    };

    const isChina = ticker === 'GCT';
    const beta = CONFIRMED_BETAS[ticker] ?? 1.0;
    const betaSource = CONFIRMED_BETAS[ticker] !== undefined ? 'CONFIRMED' : 'DEFAULT';

    let capLimitPct: number;
    let sizingTier: string;
    if (isChina) {
      capLimitPct = 0.25;
      sizingTier = 'CHINA_RISK';
    } else if (beta >= 3.0) {
      capLimitPct = 1.0;
      sizingTier = 'AAOI_TYPE_HIGH_BETA';
    } else if (beta >= 2.0) {
      capLimitPct = 1.0;
      sizingTier = 'VERY_HIGH_BETA';
    } else if (beta >= 1.5) {
      capLimitPct = 2.5;
      sizingTier = 'HIGH_BETA';
    } else if (beta >= 1.0) {
      capLimitPct = 5.0;
      sizingTier = 'MODERATE_BETA';
    } else {
      capLimitPct = 5.0;
      sizingTier = 'LOW_BETA';
    }

    const betaCapActive = positionWeight >= capLimitPct / 100;
    const effectiveExposurePct = parseFloat((positionWeight * beta * 100).toFixed(2));

    return HttpResponse.json({
      ticker,
      beta,
      beta_source: betaSource,
      position_weight_pct: parseFloat((positionWeight * 100).toFixed(2)),
      position_dollars: 0,
      effective_exposure_pct: effectiveExposurePct,
      effective_exposure_note: `${(positionWeight * 100).toFixed(1)}% position × beta ${beta} = ${effectiveExposurePct.toFixed(2)}% effective exposure`,
      beta_cap_active: betaCapActive,
      beta_cap_limit_pct: capLimitPct,
      beta_cap_reason: betaCapActive ? `Beta ${beta} — cap at ${capLimitPct}%` : null,
      sizing_tier: sizingTier,
      max_weight_pct: capLimitPct,
      adds_permitted: !betaCapActive,
      warning_level: betaCapActive ? 'RED' : 'NONE',
      warning_message: betaCapActive ? `Beta cap active — max ${capLimitPct}% NAV` : null,
      beta_source_flag: betaSource === 'DEFAULT',
    });
  }),

  // ── LEAPS ────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, ({ params }) => {
    const ticker = String(params['ticker'] ?? 'MU').toUpperCase();
    return HttpResponse.json({
      ticker,
      leaps_eligible: true,
      eligibility_undetermined: false,
      score: 88,
      tier: 'TIER_1',
      flow_confirmed: null,
      regime_state: 'CLEAR',
      regime_clears_leaps: true,
      gate_f7_active: false,
      gate_f29_passed: true,
      gate_f30_permits_leaps: true,
      iv_current: 0.45,
      iv_percentile: 0.55,
      iv_blocked: false,
      iv_alert: 'NONE',
      entry_conditions: [
        {
          condition_name: 'F33 Condition A — Calm Accumulation',
          status: 'CONFIRMED',
          met: true,
          detail: 'Calm Accumulation: drawdown=22.0% (≥20%) and VIX=16.5 in [15.0, 18.0]',
        },
        {
          condition_name: 'F33 Condition B — Washout',
          status: 'NOT_MET',
          met: false,
          detail: 'Not met: sector drawdown 10.0% < 25.0%',
        },
      ],
      conditions_met: 1,
      conditions_required: 1,
      block_reasons: [],
      warning_messages: [],
      data_age_minutes: 2,
      cache_hit: false,
    });
  }),
];
