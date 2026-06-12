import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ExtensionOverlayPanel } from '@/components/frameworks/extension-overlay-panel';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

const mocks = vi.hoisted(() => ({
  data: null as Record<string, unknown> | null,
  isLoading: false,
  isError: false,
}));

vi.mock('@/lib/hooks/use-extension-overlay', () => ({
  useExtensionOverlay: () => ({
    data: mocks.data,
    isLoading: mocks.isLoading,
    isError: mocks.isError,
    error: null,
  }),
}));

function overlay(overrides: Record<string, unknown> = {}) {
  return {
    ticker: 'MRVL',
    rsi_14: 78.4,
    rsi_7: 80.1,
    move_14d_pct: 41.2,
    move_21d_pct: 33.0,
    pct_above_20dma: 18.0,
    pct_above_50dma: 27.5,
    pct_above_200dma: 60.0,
    week_52_position_pct: 98.0,
    gap_today_pct: 1.2,
    vwap: 410.5,
    pct_vs_vwap: 3.1,
    ath: 503.0,
    ath_date: '2026-06-02',
    pct_from_ath: -18.4,
    iv_rank: null,
    td_setup: 9,
    td_setup_direction: 'SELL',
    td_countdown: 13,
    td_signal: 'SELL_COUNTDOWN_13',
    rsi_bearish_divergence: true,
    macd_bearish_cross: true,
    elliott_wave: '5',
    elliott_direction: 'UP',
    elliott_signal: 'IMPULSE_TOP_SELL',
    elliott_confidence: 75,
    gann_signal: 'BELOW_1X1_BEARISH',
    gann_below_1x1: true,
    gann_time_cycle_due: false,
    gann_nearest_support: 480,
    gann_nearest_resistance: 520,
    extension_risk_score: 9,
    extension_flag: 'EXTREME_RED',
    atlas_score: 89,
    action: 'TRIM_HEDGE',
    action_detail: 'Extremely extended — trim / hedge; no new capital.',
    data_gaps: ['IV_RANK'],
    ...overrides,
  };
}

describe('ExtensionOverlayPanel', () => {
  beforeEach(() => {
    mocks.data = overlay();
    mocks.isLoading = false;
    mocks.isError = false;
  });

  it('renders the flag, risk score, metrics and action', async () => {
    render(<ExtensionOverlayPanel ticker="MRVL" atlasScore={89} />, { wrapper: makeWrapper() });

    await waitFor(() => expect(screen.getByTestId('ext-content')).toBeInTheDocument());

    expect(screen.getByTestId('ext-flag-chip')).toHaveTextContent('EXTREME RED');
    expect(screen.getByTestId('ext-risk-score')).toHaveTextContent('9');
    expect(screen.getByTestId('ext-action')).toHaveTextContent('TRIM / HEDGE');
    expect(screen.getByTestId('ext-action-detail')).toHaveTextContent('trim / hedge');
    // Daily VWAP is surfaced; IV rank is a DATA GAP only when null.
    expect(screen.getByText('+3.1%')).toBeInTheDocument();
    expect(screen.getByText('DATA GAP')).toBeInTheDocument();
    // ATH dip shown with the ATH price.
    expect(screen.getByText('-18.4% ($503.00)')).toBeInTheDocument();
    // Technical sell signals surfaced.
    expect(screen.getByText('Sell countdown 13 ⚠')).toBeInTheDocument();
    expect(screen.getAllByText('Bearish ⚠')).toHaveLength(2); // RSI divergence + MACD cross
    // Elliott Wave + Gann surfaced.
    expect(screen.getByText('Impulse top — sell ⚠ (75%)')).toBeInTheDocument();
    expect(screen.getByText('Below 1×1 ⚠ · S/R 480–520')).toBeInTheDocument();
  });

  it('shows the IV rank value when available', async () => {
    mocks.data = overlay({ iv_rank: 82 });
    render(<ExtensionOverlayPanel ticker="MRVL" atlasScore={89} />, { wrapper: makeWrapper() });

    await waitFor(() => expect(screen.getByTestId('ext-content')).toBeInTheDocument());
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.queryByText('DATA GAP')).not.toBeInTheDocument();
  });

  it('shows a green/ADD posture for a calm, high-conviction name', async () => {
    mocks.data = overlay({
      extension_risk_score: 1,
      extension_flag: 'GREEN',
      action: 'ADD',
      action_detail: 'Buyable — conviction is high and the name is not extended.',
    });
    render(<ExtensionOverlayPanel ticker="DELL" atlasScore={92} />, { wrapper: makeWrapper() });

    await waitFor(() => expect(screen.getByTestId('ext-content')).toBeInTheDocument());
    expect(screen.getByTestId('ext-flag-chip')).toHaveTextContent('GREEN');
    expect(screen.getByTestId('ext-action')).toHaveTextContent('ADD');
  });

  it('omits the action when no atlas score is available', async () => {
    mocks.data = overlay({ atlas_score: null, action: null, action_detail: null });
    render(<ExtensionOverlayPanel ticker="MRVL" atlasScore={undefined} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(screen.getByTestId('ext-content')).toBeInTheDocument());
    expect(screen.getByTestId('ext-action')).toHaveTextContent('—');
    expect(screen.queryByTestId('ext-action-detail')).not.toBeInTheDocument();
  });
});
