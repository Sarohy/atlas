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
    expect(debug).toHaveTextContent('expiry_0_3_dte');
    expect(debug).toHaveTextContent('$4.00M');

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
});
