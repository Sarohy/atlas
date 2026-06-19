import { render, screen } from '@testing-library/react';
import { within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { F4OptionsPanel } from '@/components/frameworks/f4-options-panel';
import type { OptionsFlowResponse } from '@/lib/schemas/options-flow';

const useOptionsFlowMock = vi.fn();

vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: (...args: unknown[]) => useOptionsFlowMock(...args),
}));

function makeOptionsFlowData(overrides: Partial<OptionsFlowResponse> = {}): OptionsFlowResponse {
  return {
    ticker: 'ASML',
    f4_score: 75,
    f4_grade: 'BUY',
    dark_pool_score: 60,
    options_flow_score: 75,
    dark_pool_net_flow_usd: 1_000_000,
    options_net_flow_usd: 4_000_000,
    market_cap_usd: 300_000_000_000,
    market_cap_tier: 'LARGE',
    flow_direction: 'BULLISH',
    data_source: 'OPTIONS_ONLY',
    data_gap_reason: null,
    lookback_sessions: 2,
    dark_pool_prints_count: 10,
    dark_pool_large_buy_count: 1,
    largest_dark_pool_buy_usd: 2_000_000,
    largest_options_buy_usd: 12_000_000,
    dark_pool_state: 'NEUTRAL_MIXED',
    clearance: 'WATCH',
    hedge_structure: 'NONE',
    bullish_share: 0.75,
    f4_state: 'Bullish',
    f4_add_impact: 'Add allowed only if F4a, VWAP, cluster, size & regime gates clear',
    dark_pool_confidence: 'High - full coverage',
    live_tape_state: 'Bullish persistent',
    persistence_state: 'Bullish',
    flow_monitor_action: 'WATCH',
    flow_monitor_reason: null,
    raw_bull_premium_usd: 10_000_000,
    raw_bear_premium_usd: 2_000_000,
    raw_bullish_share: 10 / 12,
    raw_largest_bullish_print_usd: 12_000_000,
    raw_largest_call_ask_print_usd: 10_000_000,
    declassified_premium_by_reason: { expiry_0_3_dte: 4_000_000 },
    adjusted_bull_premium_usd: 6_000_000,
    adjusted_bear_premium_usd: 2_000_000,
    adjusted_bullish_share: 0.75,
    adjusted_largest_bullish_print_usd: 6_000_000,
    f4b_score_input_source: 'ADJUSTED',
    f4b_universe_source: 'UW_ALERTS_2_SESSION',
    f4b_universe_total_alerts: 12,
    f4b_universe_directional_alerts: 10,
    f4b_universe_excluded_alerts: 2,
    raw_call_ask_premium_usd: 10_000_000,
    raw_call_bid_premium_usd: 1_000_000,
    raw_put_ask_premium_usd: 2_000_000,
    raw_put_bid_premium_usd: 4_000_000,
    live_pulse_score: 88,
    live_pulse_state: 'TACTICAL_BULLISH_TRIGGER',
    ...overrides,
  } as OptionsFlowResponse;
}

describe('F4OptionsPanel', () => {
  it('renders F4b debug transparency fields when backend supplies them', () => {
    useOptionsFlowMock.mockReturnValue({
      data: makeOptionsFlowData(),
      isFetching: false,
      isError: false,
      error: null,
    });

    render(<F4OptionsPanel ticker="ASML" />);

    const debug = screen.getByTestId('f4b-debug');
    expect(debug).toHaveTextContent('Raw Bull Premium');
    expect(debug).toHaveTextContent('$10.00M');
    expect(debug).toHaveTextContent('Raw Bear Premium');
    expect(debug).toHaveTextContent('$2.00M');
    expect(debug).toHaveTextContent('Raw Bull Share');
    expect(debug).toHaveTextContent('83.3%');
    expect(debug).toHaveTextContent('Raw Largest Bullish Print');
    expect(debug).toHaveTextContent('$12.00M');
    expect(debug).toHaveTextContent('Raw Largest Call-Ask Print');
    expect(debug).toHaveTextContent('$10.00M');
    expect(debug).toHaveTextContent('Adjusted Bull Premium');
    expect(debug).toHaveTextContent('$6.00M');
    expect(debug).toHaveTextContent('Adjusted Bear Premium');
    expect(debug).toHaveTextContent('$2.00M');
    expect(debug).toHaveTextContent('Adjusted Bull Share');
    expect(debug).toHaveTextContent('75.0%');
    expect(debug).toHaveTextContent('Adjusted Largest Bullish Print');
    expect(debug).toHaveTextContent('$6.00M');
    expect(debug).toHaveTextContent('Final F4b Score');
    expect(debug).toHaveTextContent('75');
    expect(debug).toHaveTextContent('Final score input');
    expect(debug).toHaveTextContent('ADJUSTED');
    expect(debug).toHaveTextContent('Universe source');
    expect(debug).toHaveTextContent('UW_ALERTS_2_SESSION');
    expect(debug).toHaveTextContent('Universe alerts');
    expect(debug).toHaveTextContent('12 total · 10 directional · 2 excluded');
    expect(debug).toHaveTextContent('Raw Buckets');
    expect(debug).toHaveTextContent('call ask $10.00M');
    expect(debug).toHaveTextContent('call bid $1.00M');
    expect(debug).toHaveTextContent('put ask $2.00M');
    expect(debug).toHaveTextContent('put bid $4.00M');
    expect(debug).toHaveTextContent('expiry_0_3_dte');
    expect(debug).toHaveTextContent('$4.00M');

    expect(screen.getByTestId('f4-live-pulse')).toHaveTextContent(
      '1-day pulse: TACTICAL_BULLISH_TRIGGER (88)',
    );

    const optionsCard = screen.getByTestId('f4-indicator-options');
    expect(within(optionsCard).getByText('Largest Buy')).toBeInTheDocument();
    expect(optionsCard).toHaveTextContent('$12.00M');
  });

  it('hides the F4b debug bridge when the backend does not supply alert-derived fields', () => {
    useOptionsFlowMock.mockReturnValue({
      data: makeOptionsFlowData({
        raw_bull_premium_usd: null,
        raw_bear_premium_usd: null,
        raw_bullish_share: null,
        raw_largest_bullish_print_usd: null,
        raw_largest_call_ask_print_usd: null,
        adjusted_bull_premium_usd: null,
        adjusted_bear_premium_usd: null,
        adjusted_bullish_share: null,
        adjusted_largest_bullish_print_usd: null,
        declassified_premium_by_reason: {},
      }),
      isFetching: false,
      isError: false,
      error: null,
    });

    render(<F4OptionsPanel ticker="ASML" />);

    expect(screen.queryByTestId('f4b-debug')).not.toBeInTheDocument();
  });

  it('shows a low-confidence badge for F4a when dark-pool confidence is low', () => {
    useOptionsFlowMock.mockReturnValue({
      data: makeOptionsFlowData({ dark_pool_confidence: 'Low — 1 session only' }),
      isFetching: false,
      isError: false,
      error: null,
    });

    render(<F4OptionsPanel ticker="ASML" />);

    expect(screen.getByTestId('f4a-low-confidence-badge')).toHaveTextContent('LOW CONFIDENCE');
  });

  it('does not show the low-confidence badge when dark-pool confidence is high', () => {
    useOptionsFlowMock.mockReturnValue({
      data: makeOptionsFlowData({ dark_pool_confidence: 'High - full coverage' }),
      isFetching: false,
      isError: false,
      error: null,
    });

    render(<F4OptionsPanel ticker="ASML" />);

    expect(screen.queryByTestId('f4a-low-confidence-badge')).not.toBeInTheDocument();
  });

  it('renders DRAM ETF proxy diagnostics with bearish 1-day pulse kept separate from persistence', () => {
    useOptionsFlowMock.mockReturnValue({
      data: makeOptionsFlowData({
        ticker: 'MRVL',
        f4_score: 63,
        live_pulse_score: 28,
        live_pulse_state: 'TACTICAL_BEARISH_TRIGGER',
        f4b_score_input_source: 'ADJUSTED',
        f4b_universe_source: 'UW_ALERTS_2_SESSION',
        f4b_universe_total_alerts: 18,
        f4b_universe_directional_alerts: 14,
        f4b_universe_excluded_alerts: 4,
      }),
      isFetching: false,
      isError: false,
      error: null,
    });

    render(<F4OptionsPanel ticker="MRVL" />);

    expect(screen.getByTestId('f4-score')).toHaveTextContent('63');
    expect(screen.getByTestId('f4-live-pulse')).toHaveTextContent(
      '1-day pulse: TACTICAL_BEARISH_TRIGGER (28)',
    );
    const debug = screen.getByTestId('f4b-debug');
    expect(debug).toHaveTextContent('Final score input');
    expect(debug).toHaveTextContent('ADJUSTED');
    expect(debug).toHaveTextContent('Universe source');
    expect(debug).toHaveTextContent('UW_ALERTS_2_SESSION');
    expect(debug).toHaveTextContent('18 total · 14 directional · 4 excluded');
  });
});
