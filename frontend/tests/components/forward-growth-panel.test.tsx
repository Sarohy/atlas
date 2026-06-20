import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ForwardGrowthPanel } from '@/components/frameworks/forward-growth-panel';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

const mocks = vi.hoisted(() => ({
  data: null as Record<string, unknown> | null,
  framework: null as Record<string, unknown> | null,
}));

vi.mock('@/lib/hooks/use-forward-growth', () => ({
  useForwardGrowth: () => ({ data: mocks.data, isLoading: false, isError: false, error: null }),
}));
vi.mock('@/lib/hooks/use-framework-score', () => ({
  useFrameworkScore: () => ({ data: mocks.framework }),
}));
vi.mock('@/lib/hooks/use-fundamental', () => ({
  useFundamental: () => ({ data: { ticker: 'CRDO', f5_score: 60 } }),
}));
vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: () => ({ data: { ticker: 'CRDO', f4_score: 72 } }),
}));

function fgs(overrides: Record<string, unknown> = {}) {
  return {
    ticker: 'CRDO',
    fgs_score: 88,
    fgs_grade: 'ELITE',
    confidence_pct: 40,
    revenue_acceleration: { score: 80, source: 'alpha_vantage', yoy_pct: 157.0, accelerating: false },
    backlog_bookings: { score: 50, source: 'DATA_GAP' },
    customer_quality: { score: 50, source: 'DATA_GAP' },
    product_ramp: { score: 50, source: 'DATA_GAP' },
    tam_bottleneck: { score: 95, source: 'curated', wave: 'Optics / CPO / Photonics', status: 'ACTIVE' },
    f5_score: 60,
    f4_score: 72,
    atlas_score: 84,
    bucket: 'GROWTH_TACTICAL',
    action: 'High-flyer potential — tactical, size-capped (flow confirming)',
    data_gaps: ['BACKLOG_BOOKINGS', 'CUSTOMER_QUALITY', 'PRODUCT_RAMP'],
    ...overrides,
  };
}

describe('ForwardGrowthPanel', () => {
  beforeEach(() => {
    mocks.data = fgs();
    mocks.framework = null;
  });

  it('suppresses direct FGS and shows look-through growth for an ETF/proxy', async () => {
    mocks.framework = {
      ticker: 'CRDO',
      etf_branch: {
        route: 'THEMATIC_PROXY_ETF',
        label: 'Memory / HBM proxy basket',
        headline_label: 'BULLISH PROXY - add on reset / flow confirmation; size small.',
        timing_overlay_role: 'F4 is supportive timing only; not independent add authorization.',
        holdings_driver: 'MU, SNDK, SK Hynix, Samsung, STX, WDC, Kioxia',
        components: [],
        hedge_inputs: null,
      },
    };

    render(<ForwardGrowthPanel ticker="CRDO" atlasScore={70} />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('fgs-etf-content')).toBeInTheDocument());

    expect(screen.getByTestId('fgs-etf-direct-na')).toHaveTextContent('N/A — ETF/proxy instrument');
    expect(screen.getByText(/Look-through growth/)).toBeInTheDocument();
    expect(screen.getByText(/Bullish — Memory \/ HBM proxy basket/)).toBeInTheDocument();
    // Direct FGS bucket / AVOID card must NOT render for a proxy instrument.
    expect(screen.queryByTestId('fgs-content')).not.toBeInTheDocument();
    expect(screen.queryByTestId('fgs-bucket')).not.toBeInTheDocument();
  });

  it('renders the FGS score, grade, confidence, sub-factors and bucket', async () => {
    render(<ForwardGrowthPanel ticker="CRDO" atlasScore={84} />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('fgs-content')).toBeInTheDocument());

    expect(screen.getByTestId('fgs-grade-chip')).toHaveTextContent('ELITE');
    expect(screen.getByTestId('fgs-score')).toHaveTextContent('88');
    expect(screen.getByText('40%')).toBeInTheDocument();
    expect(screen.getByTestId('fgs-bucket')).toHaveTextContent('GROWTH TACTICAL');
    expect(screen.getByTestId('fgs-action')).toHaveTextContent('tactical');
    // DATA_GAP sub-factors annotated.
    expect(screen.getAllByText(/\(gap\)/).length).toBeGreaterThanOrEqual(3);
  });

  it('shows no bucket when the matrix could not be evaluated', async () => {
    mocks.data = fgs({ bucket: null, action: null });
    render(<ForwardGrowthPanel ticker="CRDO" atlasScore={undefined} />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('fgs-content')).toBeInTheDocument());
    expect(screen.getByTestId('fgs-bucket')).toHaveTextContent('—');
    expect(screen.queryByTestId('fgs-action')).not.toBeInTheDocument();
  });

  it('surfaces EDGAR backlog $ and customer concentration', async () => {
    mocks.data = fgs({
      backlog_bookings: { score: 95, source: 'edgar' },
      backlog_usd: 1_500_000_000,
      customer_quality: { score: 78, source: 'transcript' },
      customer_concentration_pct: null,
      customers_over_10pct: 2,
    });
    render(<ForwardGrowthPanel ticker="AAOI" atlasScore={74} />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('fgs-content')).toBeInTheDocument());
    expect(screen.getByText(/\$1\.5B RPO/)).toBeInTheDocument();
    expect(screen.getByText(/2 cust >10%/)).toBeInTheDocument();
  });

  it('shows exact top-customer % when EDGAR discloses it', async () => {
    mocks.data = fgs({
      customer_quality: { score: 72, source: 'transcript' },
      customer_concentration_pct: 42,
      customers_over_10pct: 1,
    });
    render(<ForwardGrowthPanel ticker="XYZ" atlasScore={70} />, { wrapper: makeWrapper() });
    await waitFor(() => expect(screen.getByTestId('fgs-content')).toBeInTheDocument());
    expect(screen.getByText(/top cust 42%/)).toBeInTheDocument();
  });
});
