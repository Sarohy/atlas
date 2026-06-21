import { render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FrameworkScorePanel } from '@/components/frameworks/framework-score-panel';
import type { ExtensionOverlayResponse } from '@/lib/schemas/extension-overlay';
import type { ExtensionWashoutResponse } from '@/lib/schemas/extension-washout';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';
import type { OptionsFlowResponse } from '@/lib/schemas/options-flow';
import type { Section16Result } from '@/lib/schemas/section16';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

const mockState = vi.hoisted(() => ({
  f8BuyingBonus: 0,
  frameworkScoreData: undefined as FrameworkScoreResponse | undefined,
  momentumData: undefined as { ticker: string; f1_score: number } | undefined,
  earningsData: undefined as { ticker: string; f2_score: number } | undefined,
  analystData: undefined as { ticker: string; f3_score: number } | undefined,
  optionsFlowData: undefined as OptionsFlowResponse | undefined,
  fundamentalData: undefined as { ticker: string; f5_score: number; f5_grade: string } | undefined,
  framework8Data: undefined as
    | {
        ticker: string;
        buying_bonus: number;
        clustered_selling_note: string | null;
        source: string;
      }
    | undefined,
  extensionOverlayData: undefined as ExtensionOverlayResponse | undefined,
  extensionWashoutData: undefined as ExtensionWashoutResponse | undefined,
  section16Data: undefined as Section16Result | undefined,
}));

vi.mock('@/lib/hooks/use-framework-score', () => ({
  useFrameworkScore: () => ({
    data: mockState.frameworkScoreData,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock('@/lib/hooks/use-momentum', () => ({
  useMomentum: () => ({
    data: mockState.momentumData,
  }),
}));

vi.mock('@/lib/hooks/use-earnings', () => ({
  useEarnings: () => ({
    data: mockState.earningsData,
  }),
}));

vi.mock('@/lib/hooks/use-analyst', () => ({
  useAnalyst: () => ({
    data: mockState.analystData,
  }),
}));

vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: () => ({
    data: mockState.optionsFlowData,
  }),
}));

vi.mock('@/lib/hooks/use-fundamental', () => ({
  useFundamental: () => ({
    data: mockState.fundamentalData,
  }),
}));

vi.mock('@/lib/hooks/use-framework8', () => ({
  useFramework8: () => ({
    data: mockState.framework8Data,
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
        score: 64,
        weight: 0.25,
        contribution: 16,
        grade: 'BUY',
        available: true,
      },
      {
        key: 'f3',
        name: 'Analyst Sentiment',
        score: 66,
        weight: 0.15,
        contribution: 9.9,
        grade: 'BUY',
        available: true,
      },
      {
        key: 'f4',
        name: 'Options Flow',
        score: 74,
        weight: 0.15,
        contribution: 11.1,
        grade: 'BUY',
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
    raw_total: 71,
    final_score: 71,
    action: 'HOLD',
    action_tone: 'tone-yellow',
    f5_blocked: false,
    f5_raw_score: null,
    f8_buying_bonus: mockState.f8BuyingBonus,
    f8_clustered_selling_note: null,
    etf_branch: null,
    intl_branch: null,
    flags: [],
    degraded: false,
    f4_data_gap_badge: null,
    f4_data_gap_message: null,
    f4_data_gap_tooltip: null,
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

describe('FrameworkScorePanel', () => {
  beforeEach(() => {
    mockState.f8BuyingBonus = 0;
    mockState.frameworkScoreData = makeFrameworkScoreData();
    mockState.momentumData = { ticker: 'AAPL', f1_score: 93 };
    mockState.earningsData = { ticker: 'AAPL', f2_score: 70 };
    mockState.analystData = { ticker: 'AAPL', f3_score: 60 };
    mockState.optionsFlowData = makeOptionsFlowData();
    mockState.fundamentalData = { ticker: 'AAPL', f5_score: 77, f5_grade: 'WEAK' };
    mockState.framework8Data = {
      ticker: 'AAPL',
      buying_bonus: 0,
      clustered_selling_note: null,
      source: 'default',
    };
    mockState.extensionOverlayData = makeExtensionOverlayData();
    mockState.extensionWashoutData = makeExtensionWashoutData();
    mockState.section16Data = makeSection16Data();
  });

  it('renders factor rows from the same F1-F5 scores shown in the detailed cards', async () => {
    render(<FrameworkScorePanel ticker="AAPL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(within(screen.getByTestId('fws-factor-f1')).getByText('93')).toBeInTheDocument();
    expect(within(screen.getByTestId('fws-factor-f2')).getByText('70')).toBeInTheDocument();
    expect(within(screen.getByTestId('fws-factor-f3')).getByText('60')).toBeInTheDocument();
    expect(within(screen.getByTestId('fws-factor-f4')).getByText('74')).toBeInTheDocument();
    expect(within(screen.getByTestId('fws-factor-f5')).getByText('77')).toBeInTheDocument();
    expect(screen.getByText('71.60')).toBeInTheDocument();
    expect(screen.getByTestId('fws-final-score-calc')).toHaveTextContent('72');
    expect(screen.getByTestId('fws-score')).toHaveTextContent('72');
  });

  it('does not apply the regime modifier — the score is the pure framework score', async () => {
    render(<FrameworkScorePanel ticker="AAPL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    // Headline equals the framework score; there is no regime-adjusted row.
    expect(screen.getByTestId('fws-score')).toHaveTextContent('72');
    expect(screen.getByTestId('fws-final-score-calc')).toHaveTextContent('72');
    expect(screen.getByText('Framework score')).toBeInTheDocument();
    expect(screen.queryByTestId('fws-regime-adjusted-score')).not.toBeInTheDocument();
    expect(screen.queryByText('Displayed after regime modifier')).not.toBeInTheDocument();
  });

  it('folds the F8 insider-buying bonus into the framework score (matches backend)', async () => {
    // raw_total from overrides = 71.6. With a +5 F8 bonus the backend computes
    // round(71.6 + 5) = 77; the frontend must match rather than showing the
    // advertised "+5" caption without applying it (round(71.6)=72).
    mockState.f8BuyingBonus = 5;
    mockState.frameworkScoreData = makeFrameworkScoreData({ f8_buying_bonus: 5 });
    mockState.framework8Data = {
      ticker: 'AAPL',
      buying_bonus: 5,
      clustered_selling_note: null,
      source: 'default',
    };

    render(<FrameworkScorePanel ticker="AAPL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-f8-bonus-note')).toHaveTextContent('+5');
    expect(screen.getByTestId('fws-final-score-calc')).toHaveTextContent('77');
    expect(screen.getByTestId('fws-score')).toHaveTextContent('77');
  });

  it('keeps the normal tier headline when flow is confirmed and no major gaps exist', async () => {
    render(<FrameworkScorePanel ticker="AAPL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent('GTC ADDS PERMITTED');
    expect(screen.getByTestId('fws-f4-summary')).toHaveTextContent(
      'F4: 74 - Bullish / Add Pending Gates',
    );
    expect(screen.getByTestId('fws-score')).toHaveClass('is-blue');
  });

  it('caps a T2 quality-pass headline when flow confirmation is missing or neutral', async () => {
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
    mockState.momentumData = { ticker: 'VRT', f1_score: 88 };
    mockState.earningsData = { ticker: 'VRT', f2_score: 80 };
    mockState.analystData = { ticker: 'VRT', f3_score: 78 };
    mockState.fundamentalData = { ticker: 'VRT', f5_score: 85, f5_grade: 'BUY' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'VRT',
      f4_score: 59,
      f4_state: 'Neutral-constructive',
      flow_monitor_action: 'WATCH',
      live_tape_state: 'Data gap',
      persistence_state: 'Neutral-constructive',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({ ticker: 'VRT', action: 'ADD' });
    mockState.extensionWashoutData = makeExtensionWashoutData({
      ticker: 'VRT',
      state: 'WAIT',
      data_gaps: ['OPTIONS', 'DP', 'F4', 'FLOW_MONITOR'],
    });

    render(<FrameworkScorePanel ticker="VRT" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'WATCH / STARTER ONLY - FLOW CONFIRMATION REQUIRED',
    );
    expect(screen.getByTestId('fws-action')).not.toHaveTextContent('GTC ADDS PERMITTED');
    expect(screen.getByTestId('fws-f4-summary')).toHaveTextContent(
      'F4: 59 - Neutral-Constructive / Watch',
    );
    expect(screen.getByTestId('fws-score')).toHaveClass('is-blue');
  });

  it('keeps no-fresh-add headline when extension overlay blocks despite flow confirmation', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'MRVL',
      final_score: 76,
      raw_total: 76,
    });
    mockState.momentumData = { ticker: 'MRVL', f1_score: 86 };
    mockState.earningsData = { ticker: 'MRVL', f2_score: 78 };
    mockState.analystData = { ticker: 'MRVL', f3_score: 74 };
    mockState.fundamentalData = { ticker: 'MRVL', f5_score: 82, f5_grade: 'BUY' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MRVL',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
      live_tape_state: 'Bullish persistent',
      persistence_state: 'Bullish',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MRVL',
      action: 'HOLD_TRIM',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'MRVL' });
    mockState.section16Data = makeSection16Data({ ticker: 'MRVL', track: 'TRACK_B' });

    render(<FrameworkScorePanel ticker="MRVL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'HOLD / WATCH - EXTENSION BLOCK / NO FRESH ADD',
    );
    expect(screen.getByTestId('fws-action')).not.toHaveTextContent('GTC ADDS PERMITTED');
  });

  it('uses TREND extension headline for track A names instead of hard extension block', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'MRVL',
      final_score: 76,
      raw_total: 76,
    });
    mockState.momentumData = { ticker: 'MRVL', f1_score: 86 };
    mockState.earningsData = { ticker: 'MRVL', f2_score: 78 };
    mockState.analystData = { ticker: 'MRVL', f3_score: 74 };
    mockState.fundamentalData = { ticker: 'MRVL', f5_score: 82, f5_grade: 'BUY' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MRVL',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
      live_tape_state: 'Bullish persistent',
      persistence_state: 'Bullish',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MRVL',
      action: 'HOLD_TRIM',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'MRVL' });
    mockState.section16Data = makeSection16Data({ ticker: 'MRVL', track: 'TRACK_A' });

    render(<FrameworkScorePanel ticker="MRVL" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'EXTENDED TREND - NO MARKET CHASE; LADDER/PROTECT/VWAP CONFIRM',
    );
    expect(screen.getByTestId('fws-action')).not.toHaveTextContent(
      'EXTENSION BLOCK / NO FRESH ADD',
    );
  });

  it('caps an elite headline to core hold when extension and event-risk blocks are active', async () => {
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
    mockState.momentumData = { ticker: 'MU', f1_score: 98 };
    mockState.earningsData = { ticker: 'MU', f2_score: 100 };
    mockState.analystData = { ticker: 'MU', f3_score: 96 };
    mockState.fundamentalData = { ticker: 'MU', f5_score: 91, f5_grade: 'STRONG BUY' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'MU',
      f4_score: 52,
      f4_state: 'Neutral',
      flow_monitor_action: 'WATCH',
      live_tape_state: 'Mixed / structured',
      persistence_state: 'Neutral',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({
      ticker: 'MU',
      extension_flag: 'RED',
      action: 'HOLD_TRIM',
      pct_vs_vwap: -0.6,
      iv_rank: 96,
      td_signal: 'SELL_SETUP',
    });
    mockState.extensionWashoutData = makeExtensionWashoutData({
      ticker: 'MU',
      state: 'WAIT',
      reason: 'Event risk ahead',
      negative_catalyst: true,
    });

    render(<FrameworkScorePanel ticker="MU" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'T1 ELITE / CORE HOLD - LEAPS ONLY ON RESET',
    );
    expect(screen.getByTestId('fws-action')).not.toHaveTextContent('T1 ELITE — LEAPS ELIGIBLE');
    expect(screen.getByTestId('fws-score')).toHaveClass('is-green');
  });

  it('shows strict hard-block hold/watch label when F5 blocks but flow is not deteriorating', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'CRWV',
      final_score: 86,
      raw_total: 86,
      f5_blocked: true,
    });
    mockState.momentumData = { ticker: 'CRWV', f1_score: 93 };
    mockState.earningsData = { ticker: 'CRWV', f2_score: 70 };
    mockState.analystData = { ticker: 'CRWV', f3_score: 60 };
    mockState.fundamentalData = { ticker: 'CRWV', f5_score: 22, f5_grade: 'DISTRESSED' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'CRWV',
      f4_score: 66,
      flow_monitor_action: 'WATCH',
    });
    mockState.extensionOverlayData = makeExtensionOverlayData({ ticker: 'CRWV', action: 'ADD' });
    mockState.extensionWashoutData = makeExtensionWashoutData({ ticker: 'CRWV' });

    render(<FrameworkScorePanel ticker="CRWV" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'HOLD / WATCH - F5 HARD BLOCK / NO NEW CAPITAL',
    );
  });

  it('shows trim/reduce label when F5 blocks and flow monitor deteriorates', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'CRWV',
      final_score: 78,
      raw_total: 78,
      f5_blocked: true,
    });
    mockState.momentumData = { ticker: 'CRWV', f1_score: 88 };
    mockState.earningsData = { ticker: 'CRWV', f2_score: 75 };
    mockState.analystData = { ticker: 'CRWV', f3_score: 72 };
    mockState.fundamentalData = { ticker: 'CRWV', f5_score: 24, f5_grade: 'DISTRESSED' };
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

    render(<FrameworkScorePanel ticker="CRWV" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent('TRIM / REDUCE');
  });

  it('shows degraded composite headline and non-authorizing F4 wording when degraded', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'DRAM',
      final_score: 72,
      raw_total: 72,
      degraded: true,
      factors: [
        {
          key: 'f1',
          name: 'Momentum',
          score: 50,
          weight: 0.2,
          contribution: 10,
          grade: 'N/A',
          available: false,
        },
        {
          key: 'f2',
          name: 'Earnings Quality',
          score: 50,
          weight: 0.25,
          contribution: 12.5,
          grade: 'N/A',
          available: false,
        },
        {
          key: 'f3',
          name: 'Analyst Sentiment',
          score: 50,
          weight: 0.15,
          contribution: 7.5,
          grade: 'NO COVERAGE',
          available: false,
        },
        {
          key: 'f4',
          name: 'Options Flow Persistence',
          score: 72,
          weight: 0.15,
          contribution: 10.8,
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
    });
    mockState.momentumData = { ticker: 'DRAM', f1_score: 50 };
    mockState.earningsData = { ticker: 'DRAM', f2_score: 50 };
    mockState.analystData = { ticker: 'DRAM', f3_score: 50 };
    mockState.fundamentalData = { ticker: 'DRAM', f5_score: 77, f5_grade: 'WEAK' };
    mockState.optionsFlowData = makeOptionsFlowData({
      ticker: 'DRAM',
      f4_score: 72,
      flow_monitor_action: 'ADD_PENDING_GATES',
      f4_state: 'Bullish',
    });

    render(<FrameworkScorePanel ticker="DRAM" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'DEGRADED / LOW-CONFIDENCE COMPOSITE - NO FULL EQUITY SIZING',
    );
    expect(screen.getByTestId('fws-f4-summary')).toHaveTextContent(
      'F4: 72 - Bullish / F4 bullish, not independently add-authorizing',
    );
  });

  it('uses ETF branch headline metadata when router output is present', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'DRAM',
      final_score: 70,
      raw_total: 70,
      degraded: true,
      action_tone: 'tone-blue',
      etf_branch: {
        route: 'THEMATIC_PROXY_ETF',
        label: 'Memory / HBM proxy basket',
        headline_label:
          'BULLISH PROXY - memory/HBM basket exposure. Direct company F1-F5 not applicable.',
        timing_overlay_role: 'F4 is supportive timing only; not independent add authorization.',
        holdings_driver: 'MU, SNDK, SK Hynix, Samsung, STX, WDC, Kioxia',
        components: [],
        constituents: [],
        scored_coverage_pct: null,
        coverage_note: null,
        hedge_inputs: null,
      },
      flags: ['ETF branch: thematic equity proxy basket (look-through model).'],
    });
    mockState.optionsFlowData = makeOptionsFlowData({ ticker: 'DRAM' });
    mockState.momentumData = { ticker: 'DRAM', f1_score: 95 };
    mockState.earningsData = { ticker: 'DRAM', f2_score: 50 };
    mockState.analystData = { ticker: 'DRAM', f3_score: 50 };
    mockState.fundamentalData = { ticker: 'DRAM', f5_score: 50, f5_grade: 'N/A' };
    mockState.framework8Data = {
      ticker: 'DRAM',
      buying_bonus: 0,
      clustered_selling_note: null,
      source: 'default',
    };

    render(<FrameworkScorePanel ticker="DRAM" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fws-action')).toHaveTextContent(
      'BULLISH PROXY - memory/HBM basket exposure. Direct company F1-F5 not applicable.',
    );
    expect(screen.getByTestId('fws-score')).toHaveTextContent('70');
    expect(screen.queryByTestId('fws-degraded')).not.toBeInTheDocument();
  });

  it('relabels the ETF composite as Proxy Composite and shows look-through components', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'DRAM',
      final_score: 70,
      raw_total: 70,
      degraded: true,
      action_tone: 'tone-blue',
      etf_branch: {
        route: 'THEMATIC_PROXY_ETF',
        label: 'Memory / HBM proxy basket',
        headline_label: 'BULLISH PROXY - memory/HBM basket exposure.',
        timing_overlay_role: 'F4 is supportive timing only; not independent add authorization.',
        holdings_driver: 'MU, SNDK, SK Hynix, Samsung, STX, WDC, Kioxia',
        components: [
          { name: 'Constituent look-through score', weight: 0.45, score: 76 },
          { name: 'ETF F4 / options timing', weight: 0.1, score: 65 },
        ],
        constituents: [
          { symbol: 'MU', weight_pct: 20, scored: true, note: null },
          { symbol: 'SK Hynix', weight_pct: 18, scored: false, note: 'foreign-listed' },
          { symbol: 'SNDK', weight_pct: 12, scored: true, note: null },
        ],
        scored_coverage_pct: 56,
        coverage_note: 'Scored coverage ~56% of basket weight. Weights are approximate / curated.',
        hedge_inputs: null,
      },
      flags: ['ETF branch: thematic equity proxy basket (look-through model).'],
    });
    mockState.optionsFlowData = makeOptionsFlowData({ ticker: 'DRAM', f4_score: 65 });
    mockState.fundamentalData = { ticker: 'DRAM', f5_score: 50, f5_grade: 'N/A' };

    render(<FrameworkScorePanel ticker="DRAM" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    // Title + footer use "Proxy Composite", not "Framework 1" / "Framework score".
    expect(screen.getAllByText('Proxy Composite').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('Framework score')).not.toBeInTheDocument();
    // Direct F1–F5 disclosure + look-through components reconcile to the score.
    expect(screen.getByTestId('fws-etf-direct-na')).toHaveTextContent('Direct company score: N/A');
    expect(screen.getAllByTestId('fws-etf-component').length).toBe(2);
    // Scored holdings coverage % + per-constituent scored/not-scored breakdown.
    expect(screen.getByTestId('fws-etf-coverage-pct')).toHaveTextContent('56% of basket weight');
    expect(screen.getAllByTestId('fws-etf-constituent').length).toBe(3);
    expect(screen.getByTestId('fws-etf-coverage-note')).toHaveTextContent('approximate / curated');
  });

  it('renders the INTL-3F branch for foreign/OTC names without a degraded/avoid banner', async () => {
    mockState.frameworkScoreData = makeFrameworkScoreData({
      ticker: 'LPKFF',
      final_score: 50,
      raw_total: 50,
      degraded: false,
      action: 'INTL-3F — RANK PENDING / manual review (insufficient international data)',
      action_tone: 'tone-yellow',
      intl_branch: {
        route: 'INTL_OPERATING',
        label: 'INTL-3F — International Operating Company',
        headline_label:
          'INTL-3F — RANK PENDING / manual review (insufficient international data)',
        instrument_kind: 'OTC foreign ordinary',
        coverage_label: 'INTL-DATA-GAP',
        domestic_note: 'Domestic F1–F5 not applicable.',
        f4_note: 'F4 N/A — no U.S. flow coverage (unavailable, not bearish).',
        rank_pending: true,
        size_capped: true,
        factors: [
          { key: 'i1', name: 'Business / Forward Fundamentals', score: 50, available: false, source: 'DATA_GAP' },
          { key: 'i2', name: 'Market / Momentum / Liquidity', score: 50, available: false, source: 'DATA_GAP' },
          { key: 'i3', name: 'External Confirmation', score: 50, available: false, source: 'DATA_GAP' },
        ],
        labels: ['INTL-DATA-GAP', 'NO-US-FLOW', 'FOREIGN-SOURCE-NEEDED', 'OTC-LIQUIDITY-RISK'],
        data_tasks: [
          { item: 'local financials', status: 'MISSING' },
          { item: 'options / flow availability (U.S.)', status: 'MISSING' },
        ],
      },
      flags: ['INTL router active: domestic F1–F5 not applicable; INTL-3F model drives action.'],
    });

    render(<FrameworkScorePanel ticker="LPKFF" onPreviewDetails={() => {}} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('fws-content')).toBeInTheDocument();
    });

    // Title is INTL Framework, not Framework 1; no degraded/avoid banner.
    expect(screen.getByText('INTL Framework')).toBeInTheDocument();
    expect(screen.queryByText('Framework 1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('fws-degraded')).not.toBeInTheDocument();
    // Headline = rank pending (never AVOID from missing data).
    expect(screen.getByTestId('fws-action')).toHaveTextContent('RANK PENDING');
    // INTL-3F breakdown: domestic-N/A note, labels, F4 N/A note, data tasks.
    expect(screen.getByTestId('fws-intl-domestic-na')).toHaveTextContent('Domestic F1–F5 not applicable');
    expect(screen.getByTestId('fws-intl-f4-note')).toHaveTextContent('not bearish');
    expect(screen.getAllByTestId('fws-intl-factor').length).toBe(3);
    expect(screen.getAllByTestId('fws-intl-data-task').length).toBe(2);
    expect(within(screen.getByTestId('fws-intl-labels')).getByText('NO-US-FLOW')).toBeInTheDocument();
  });
});
