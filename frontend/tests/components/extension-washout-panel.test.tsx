import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ExtensionWashoutPanel } from '@/components/frameworks/extension-washout-panel';

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

vi.mock('@/lib/hooks/use-extension-washout', () => ({
  useExtensionWashout: () => ({
    data: mocks.data,
    isLoading: mocks.isLoading,
    isError: mocks.isError,
    error: null,
  }),
}));

function washout(overrides: Record<string, unknown> = {}) {
  return {
    ticker: 'SNDK',
    state: 'ARM_PROTECTION',
    reason: 'Arm defined-risk; trim 0%.',
    rung: 'Arm Protection',
    track: 'EXTENSION',
    overshoot: 'MASSIVE',
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
    dist_50d: 53.1,
    rsi_14: 72.0,
    move_21d_pct: 28.0,
    move_14d_pct: 19.0,
    move_20d_pct: 17.0,
    dark_pool_sell_pct: 40.0,
    metric_legs: { moderate: ['50d>=25%'], extreme: [] },
    position_weight_pct: 3.1,
    target_pct: 8.0,
    below_target: true,
    breadth: null,
    breadth_watch_count: 1,
    breadth_hedge_count: 0,
    breadth_universe_size: 32,
    elasticity_tier: 'EXTREME',
    elasticity_score: 86,
    elasticity_confidence: 'HIGH',
    elasticity_event_count: 3,
    plus40_state: 'ARM_PROTECTION',
    plus40_behavior: 'protect only',
    elasticity_ladder: [40, 65, 85],
    sizing_guidance: 'Core-size; push trim tranches to +70/+80; widest no-chase band.',
    elasticity_provisional: false,
    elasticity_watch_promote: false,
    elasticity_excluded_from_recalibration: false,
    elasticity_hard_override: false,
    rv20: 90,
    rv60: 98,
    beta: 1.8,
    elasticity_data_gaps: ['SHORT_INTEREST', 'FLOAT', 'OPTIONS', 'DP', 'F4', 'FLOW_MONITOR'],
    data_gaps: [],
    ...overrides,
  };
}

describe('ExtensionWashoutPanel', () => {
  beforeEach(() => {
    mocks.data = washout();
    mocks.isLoading = false;
    mocks.isError = false;
  });

  it('renders the headline state, rung, track and metrics', async () => {
    render(<ExtensionWashoutPanel ticker="SNDK" />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('washout-content')).toBeInTheDocument());

    expect(screen.getByTestId('washout-state')).toHaveTextContent('Arm Protection');
    expect(screen.getByTestId('washout-track')).toHaveTextContent('Extension-managed');
    expect(screen.getByText('+53.1%')).toBeInTheDocument();
    // Overshoot Elasticity (v2.1) surfaced.
    expect(screen.getByTestId('washout-elasticity-tier')).toHaveTextContent('Extreme');
    expect(screen.getByText('protect only')).toBeInTheDocument();
    expect(screen.getByTestId('washout-elasticity-gaps')).toHaveTextContent('FLOW_MONITOR');
  });

  it('shows the size re-label note when below target', async () => {
    mocks.data = washout({ state: 'STOP_ADD', size_relabeled: true });
    render(<ExtensionWashoutPanel ticker="VRT" />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('washout-content')).toBeInTheDocument());
    expect(screen.getByTestId('washout-size-note')).toHaveTextContent('re-labeled to Stop-Add');
  });

  it('flags trim authorization when satisfied', async () => {
    mocks.data = washout({
      state: 'TRIM',
      trim_authorized: true,
      confirmation_count: 2,
      flow_distribution: true,
      vwap_lost: true,
      below_target: false,
      position_weight_pct: 11.0,
    });
    render(<ExtensionWashoutPanel ticker="MU" />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('washout-content')).toBeInTheDocument());
    expect(screen.getByTestId('washout-trim-authorized')).toHaveTextContent('TRIM AUTHORIZED');
  });

  it('renders the book-level hedge state', async () => {
    mocks.data = washout({ state: 'BOOK_LEVEL_HEDGE', breadth: 'BREADTH_HEDGE', breadth_hedge_count: 13 });
    render(<ExtensionWashoutPanel ticker="MU" />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('washout-content')).toBeInTheDocument());
    expect(screen.getByTestId('washout-state')).toHaveTextContent('Book-Level Hedge');
  });
});
