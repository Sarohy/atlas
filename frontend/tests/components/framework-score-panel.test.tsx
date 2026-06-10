import { render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FrameworkScorePanel } from '@/components/frameworks/framework-score-panel';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

const mockState = vi.hoisted(() => ({ f8BuyingBonus: 0 }));

vi.mock('@/lib/hooks/use-framework-score', () => ({
  useFrameworkScore: () => ({
    data: {
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
      flags: [],
      degraded: false,
    },
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock('@/lib/hooks/use-momentum', () => ({
  useMomentum: () => ({
    data: { ticker: 'AAPL', f1_score: 93 },
  }),
}));

vi.mock('@/lib/hooks/use-earnings', () => ({
  useEarnings: () => ({
    data: { ticker: 'AAPL', f2_score: 70 },
  }),
}));

vi.mock('@/lib/hooks/use-analyst', () => ({
  useAnalyst: () => ({
    data: { ticker: 'AAPL', f3_score: 60 },
  }),
}));

vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: () => ({
    data: { ticker: 'AAPL', f4_score: 74 },
  }),
}));

vi.mock('@/lib/hooks/use-fundamental', () => ({
  useFundamental: () => ({
    data: { ticker: 'AAPL', f5_score: 77, f5_grade: 'WEAK' },
  }),
}));

vi.mock('@/lib/hooks/use-framework8', () => ({
  useFramework8: () => ({
    data: { ticker: 'AAPL', buying_bonus: 0, clustered_selling_note: null, source: 'default' },
    isLoading: false,
    isError: false,
  }),
}));

describe('FrameworkScorePanel', () => {
  beforeEach(() => {
    mockState.f8BuyingBonus = 0;
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
});
