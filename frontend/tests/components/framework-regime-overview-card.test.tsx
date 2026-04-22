import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FrameworkRegimeOverviewCard } from '@/components/frameworks/framework-regime-overview-card';

vi.mock('@/lib/stores/framework-store', () => ({
  useFrameworkStore: (selector: (state: { activeTicker: string }) => string) =>
    selector({ activeTicker: 'AAPL' }),
}));

vi.mock('@/lib/hooks/use-tickers', () => ({
  useTickers: () => ({
    data: [{ ticker: 'AAPL' }],
  }),
}));

vi.mock('@/lib/hooks/use-regime-modifier', () => ({
  useRegimeModifier: () => ({
    data: {
      effective_regime: 'SOFT CAUTION',
      adjusted_score: 74,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/stores/geopolitical-store', () => ({
  useGeopoliticalStore: (selector: (state: { geopoliticalState: string }) => string) =>
    selector({ geopoliticalState: 'ACTIVE_RISK' }),
}));

describe('FrameworkRegimeOverviewCard', () => {
  it('renders the live Framework 2 regime value in the overview slot', () => {
    render(<FrameworkRegimeOverviewCard />);

    expect(screen.getByTestId('framework-regime-overview-value')).toHaveTextContent(
      'SOFT CAUTION',
    );
    expect(screen.queryByText('Framework 2 Regime')).not.toBeInTheDocument();
    expect(screen.queryByText('AAPL · adjusted score 74')).not.toBeInTheDocument();
  });
});
