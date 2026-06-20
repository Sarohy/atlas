import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FrameworkScoreOverviewCard } from '@/components/frameworks/framework-score-overview-card';
import type { ExtensionOverlayResponse } from '@/lib/schemas/extension-overlay';
import type { ExtensionWashoutResponse } from '@/lib/schemas/extension-washout';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';
import type { OptionsFlowResponse } from '@/lib/schemas/options-flow';
import type { Section16Result } from '@/lib/schemas/section16';

const mockState = vi.hoisted(() => ({
  activeTicker: 'AAPL',
  frameworkScoreData: undefined as FrameworkScoreResponse | undefined,
  optionsFlowData: undefined as OptionsFlowResponse | undefined,
  extensionOverlayData: undefined as ExtensionOverlayResponse | undefined,
  extensionWashoutData: undefined as ExtensionWashoutResponse | undefined,
  section16Data: undefined as Section16Result | undefined,
}));

vi.mock('@/lib/stores/framework-store', () => ({
  useFrameworkStore: (selector: (state: { activeTicker: string }) => string) =>
    selector({ activeTicker: mockState.activeTicker }),
}));

vi.mock('@/lib/hooks/use-framework-score', () => ({
  useFrameworkScore: () => ({
    data: mockState.frameworkScoreData,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: () => ({
    data: mockState.optionsFlowData,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/hooks/use-extension-overlay', () => ({
  useExtensionOverlay: () => ({
    data: mockState.extensionOverlayData,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/hooks/use-extension-washout', () => ({
  useExtensionWashout: () => ({
    data: mockState.extensionWashoutData,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/hooks/use-section16', () => ({
  useSection16: () => ({
    data: mockState.section16Data,
    isLoading: false,
    isError: false,
  }),
}));

function makeFrameworkScoreData(
  overrides: Partial<FrameworkScoreResponse> = {},
): FrameworkScoreResponse {
  return {
    ticker: 'AAPL',
    factors: [
      {
        key: 'f1',
        name: 'Momentum',
        score: 93,
        weight: 0.2,
        contribution: 18.6,
        grade: 'STRONG BUY',
        available: true,
      },
      {
        key: 'f2',
        name: 'Earnings Quality',
        score: 70,
        weight: 0.25,
        contribution: 17.5,
        grade: 'BUY',
        available: true,
      },
      {
        key: 'f3',
        name: 'Analyst Sentiment',
        score: 60,
        weight: 0.15,
        contribution: 9,
        grade: 'BUY',
        available: true,
      },
      {
        key: 'f4',
        name: 'Options Flow Persistence',
        score: 74,
        weight: 0.15,
        contribution: 11.1,
        grade: 'Bullish',
        available: true,
        flow_monitor_action: 'ADD_PENDING_GATES',
      },
      {
        key: 'f5',
        name: 'Fundamental Quality',
        score: 77,
        weight: 0.2,
        contribution: 15.4,
        grade: 'WEAK',
        available: true,
      },
    ],
    raw_total: 71.6,
    final_score: 72,
    action: 'GTC ADDS PERMITTED',
    action_tone: 'tone-blue',
    f5_blocked: false,
    flags: [],
    degraded: false,
    f4_data_gap_badge: null,
    f4_data_gap_message: null,
    f4_data_gap_tooltip: null,
    f5_raw_score: null,
    f8_buying_bonus: 0,
    f8_clustered_selling_note: null,
    ...overrides,
  };
}

function makeOptionsFlowData(overrides: Partial<OptionsFlowResponse> = {}): OptionsFlowResponse {
  return {
    ticker: 'AAPL',
    f4_score: 74,
    f4_grade: 'BUY',
    dark_pool_score: 60,
    options_flow_score: 74,
    dark_pool_net_flow_usd: 1,
    options_net_flow_usd: 1,
    market_cap_usd: 1,
    market_cap_tier: 'LARGE',
    flow_direction: 'BULLISH',
    data_source: 'OPTIONS_ONLY',
    data_gap_reason: null,
    lookback_sessions: 2,
    dark_pool_prints_count: 1,
    dark_pool_large_buy_count: 0,
    largest_dark_pool_buy_usd: null,
    largest_options_buy_usd: null,
    dark_pool_state: 'NEUTRAL_MIXED',
    clearance: 'WATCH',
    hedge_structure: 'NONE',
    f4_state: 'Bullish',
    f4_add_impact: 'Add allowed only if F4a, VWAP, cluster, size & regime gates clear',
    dark_pool_confidence: 'High - full coverage',
    live_tape_state: 'Bullish persistent',
    persistence_state: 'Bullish',
    flow_monitor_action: 'ADD_PENDING_GATES',
    flow_monitor_reason: null,
    ...overrides,
  } as OptionsFlowResponse;
}

function makeExtensionOverlayData(
  overrides: Partial<ExtensionOverlayResponse> = {},
): ExtensionOverlayResponse {
  return {
    ticker: 'AAPL',
    extension_risk_score: 10,
    extension_flag: 'GREEN',
    atlas_score: 72,
    action: 'ADD',
    action_detail: 'OK',
    data_gaps: [],
    ...overrides,
  } as ExtensionOverlayResponse;
}

function makeExtensionWashoutData(
  overrides: Partial<ExtensionWashoutResponse> = {},
): ExtensionWashoutResponse {
  return {
    ticker: 'AAPL',
    state: 'WAIT',
    reason: 'Waiting',
    rung: 'WAIT',
    track: 'extension',
    overshoot: 'moderate',
    low_confidence: false,
    trim_authorized: false,
    size_relabeled: false,
    confirmation_count: 0,
    confirmation_present: [],
    flow_distribution: false,
    vwap_lost: false,
    group_rolling: false,
    absorption: false,
    hard_override: false,
    negative_catalyst: false,
    metric_legs: { moderate: [], extreme: [] },
    target_pct: 0,
    breadth_watch_count: 0,
    breadth_hedge_count: 0,
    breadth_universe_size: 0,
    elasticity_tier: 'UNKNOWN',
    elasticity_confidence: 'LOW',
    elasticity_event_count: 0,
    plus40_state: 'ARM_PROTECTION',
    plus40_behavior: '',
    elasticity_ladder: [],
    sizing_guidance: '',
    elasticity_provisional: false,
    elasticity_watch_promote: false,
    elasticity_excluded_from_recalibration: false,
    elasticity_hard_override: false,
    data_gaps: [],
    ...overrides,
  } as ExtensionWashoutResponse;
}

function makeSection16Data(overrides: Partial<Section16Result> = {}): Section16Result {
  return {
    ticker: 'AAPL',
    track: 'UNASSIGNED',
    gate: 'UNKNOWN',
    rule1: null,
    rule2: null,
    rule3: null,
    rule4: null,
    override: null,
    override_used: false,
    evaluated_at: '2026-01-01T00:00:00Z',
    notes: null,
    ...overrides,
  };
}

describe('FrameworkScoreOverviewCard', () => {
  it('keeps the normal tier headline when flow is confirmed and no major gaps exist', () => {
    mockState.activeTicker = 'AAPL';
    mockState.frameworkScoreData = makeFrameworkScoreData();
    mockState.optionsFlowData = makeOptionsFlowData();
    mockState.extensionOverlayData = makeExtensionOverlayData();
    mockState.extensionWashoutData = makeExtensionWashoutData();

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent('GTC ADDS PERMITTED');
  });

  it('caps the overview headline when flow confirmation is missing or neutral', () => {
    mockState.activeTicker = 'VRT';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'VRT',
      final_score: 79,
      raw_total: 79,
      f4_data_gap_badge: 'DATA GAPS: OPTIONS / DP / F4 / FLOW_MONITOR',
      factors: [
        {
          key: 'f1',
          name: 'Momentum',
          score: 88,
          weight: 0.2,
          contribution: 17.6,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f2',
          name: 'Earnings Quality',
          score: 80,
          weight: 0.25,
          contribution: 20,
          grade: 'BUY',
          available: true,
        },
        {
          key: 'f3',
          name: 'Analyst Sentiment',
          score: 78,
          weight: 0.15,
          contribution: 11.7,
          grade: 'BUY',
          available: true,
        },
        {
          key: 'f4',
          name: 'Options Flow Persistence',
          score: 59,
          weight: 0.15,
          contribution: 8.85,
          grade: 'Neutral-Constructive',
          available: true,
          flow_monitor_action: 'WATCH',
        },
        {
          key: 'f5',
          name: 'Fundamental Quality',
          score: 85,
          weight: 0.2,
          contribution: 17,
          grade: 'BUY',
          available: true,
        },
      ],
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'VRT',
      f4_score: 59,
      f4_state: 'Neutral-constructive',
      flow_monitor_action: 'WATCH',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({ ticker: 'VRT', action: 'ADD' });
    mockState.extensionWashoutData = makeExtensionWashoutData({
      ticker: 'VRT',
      data_gaps: ['OPTIONS', 'DP', 'F4', 'FLOW_MONITOR'],
    });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'WATCH / STARTER ONLY - FLOW CONFIRMATION REQUIRED',
    );
    expect(screen.getByTestId('fws-overview-card')).not.toHaveTextContent('GTC ADDS PERMITTED');
  });

  it('keeps overview no-fresh-add headline when extension overlay blocks despite flow confirmation', () => {
    mockState.activeTicker = 'MRVL';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'MRVL',
      final_score: 76,
      raw_total: 76,
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MRVL',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MRVL',
      action: 'HOLD_TRIM',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'MRVL' });
    mockState.section16Data = makeSection16Data({ ticker: 'MRVL', track: 'TRACK_B' });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'HOLD / WATCH - EXTENSION BLOCK / NO FRESH ADD',
    );
  });

  it('uses TREND extension headline for track A names in overview', () => {
    mockState.activeTicker = 'MRVL';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'MRVL',
      final_score: 76,
      raw_total: 76,
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MRVL',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MRVL',
      action: 'HOLD_TRIM',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'MRVL' });
    mockState.section16Data = makeSection16Data({ ticker: 'MRVL', track: 'TRACK_A' });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'EXTENDED TREND - NO MARKET CHASE; LADDER/PROTECT/VWAP CONFIRM',
    );
    expect(screen.getByTestId('fws-overview-card')).not.toHaveTextContent(
      'EXTENSION BLOCK / NO FRESH ADD',
    );
  });

  it('caps the overview elite headline when extension and event-risk blocks are active', () => {
    mockState.activeTicker = 'MU';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'MU',
      final_score: 86,
      raw_total: 86,
      factors: [
        {
          key: 'f1',
          name: 'Momentum',
          score: 98,
          weight: 0.2,
          contribution: 19.6,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f2',
          name: 'Earnings Quality',
          score: 100,
          weight: 0.25,
          contribution: 25,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f3',
          name: 'Analyst Sentiment',
          score: 96,
          weight: 0.15,
          contribution: 14.4,
          grade: 'STRONG BUY',
          available: true,
        },
        {
          key: 'f4',
          name: 'Options Flow Persistence',
          score: 52,
          weight: 0.15,
          contribution: 7.8,
          grade: 'Neutral',
          available: true,
          flow_monitor_action: 'WATCH',
        },
        {
          key: 'f5',
          name: 'Fundamental Quality',
          score: 91,
          weight: 0.2,
          contribution: 18.2,
          grade: 'STRONG BUY',
          available: true,
        },
      ],
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MU',
      f4_score: 52,
      f4_state: 'Neutral',
      flow_monitor_action: 'WATCH',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MU',
      extension_flag: 'RED',
      action: 'HOLD_TRIM',
      iv_rank: 96,
      pct_vs_vwap: -0.6,
      td_signal: 'SELL_SETUP',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({
      ticker: 'MU',
      negative_catalyst: true,
      reason: 'Event risk ahead',
    });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'T1 ELITE / CORE HOLD - LEAPS ONLY ON RESET',
    );
  });

  it('shows hold/watch hard-block label when F5 blocks but flow is not deteriorating', () => {
    mockState.activeTicker = 'CRWV';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'CRWV',
      final_score: 86,
      raw_total: 86,
      f5_blocked: true,
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'CRWV',
      f4_score: 66,
      flow_monitor_action: 'WATCH',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({ ticker: 'CRWV', action: 'ADD' });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'CRWV' });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'HOLD / WATCH - F5 HARD BLOCK / NO NEW CAPITAL',
    );
  });

  it('shows trim/reduce label when F5 blocks and flow deteriorates', () => {
    mockState.activeTicker = 'CRWV';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'CRWV',
      final_score: 78,
      raw_total: 78,
      f5_blocked: true,
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'CRWV',
      f4_score: 41,
      flow_monitor_action: 'TRIM_WATCH',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'CRWV',
      action: 'HOLD_TRIM',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'CRWV' });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent('TRIM / REDUCE');
  });

  it('shows degraded composite headline when score is degraded', () => {
    mockState.activeTicker = 'DRAM';
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'DRAM',
      final_score: 72,
      raw_total: 72,
      degraded: true,
    });
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'DRAM',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
    });

    render(<FrameworkScoreOverviewCard />);

    expect(screen.getByTestId('fws-overview-card')).toHaveTextContent(
      'DEGRADED / LOW-CONFIDENCE COMPOSITE - NO FULL EQUITY SIZING',
    );
  });
});
