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

const mocks = vi.hoisted(() => ({ data: null as Record<string, unknown> | null }));

vi.mock('@/lib/hooks/use-forward-growth', () => ({
  useForwardGrowth: () => ({ data: mocks.data, isLoading: false, isError: false, error: null }),
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
});
