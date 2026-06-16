import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WashoutReferencePanel } from '@/components/frameworks/washout-reference-panel';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

const mocks = vi.hoisted(() => ({ data: null as Record<string, unknown> | null, isError: false }));

vi.mock('@/lib/hooks/use-washout-reference', () => ({
  useWashoutReference: () => ({ data: mocks.data, isLoading: false, isError: mocks.isError }),
}));

describe('WashoutReferencePanel', () => {
  beforeEach(() => {
    mocks.data = {
      thresholds: [
        { key: 'arm_protection_50d', value: '40.0', group: 'Ladder (§3)' },
        { key: 'breadth_hedge_min', value: '12', group: 'Breadth (§5)' },
      ],
      exceptions: [
        {
          ticker: 'NBIS',
          track: 'BREADTH_FLOW',
          overshoot: 'SHARP_FALLER',
          elasticity_tier: 'SHARP_FALLER',
          flags: ['hard-override'],
          note: 'Sharp-faller (A4)',
        },
        {
          ticker: 'MXL',
          track: 'EXTENSION',
          overshoot: 'EXCLUDED',
          elasticity_tier: 'ANOMALY',
          flags: ['excl-recalibration'],
          note: 'Squeeze artifact',
        },
      ],
    };
    mocks.isError = false;
  });

  it('renders thresholds and risk exceptions', async () => {
    render(<WashoutReferencePanel />, { wrapper: makeWrapper() });
    await waitFor(() =>
      expect(screen.getByTestId('washout-reference-content')).toBeInTheDocument(),
    );
    expect(screen.getByText('arm_protection_50d')).toBeInTheDocument();
    expect(screen.getByTestId('washout-exception-count')).toHaveTextContent('2');
    expect(screen.getByText('hard-override')).toBeInTheDocument();
    expect(screen.getByText('excl-recalibration')).toBeInTheDocument();
  });
});
