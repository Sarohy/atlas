import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FrameworkScorePanel } from '@/components/frameworks/framework-score-panel';

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
    data: { f1_score: 93 },
  }),
}));

vi.mock('@/lib/hooks/use-earnings', () => ({
  useEarnings: () => ({
    data: { f2_score: 70 },
  }),
}));

vi.mock('@/lib/hooks/use-analyst', () => ({
  useAnalyst: () => ({
    data: { f3_score: 60 },
  }),
}));

vi.mock('@/lib/hooks/use-options-flow', () => ({
  useOptionsFlow: () => ({
    data: { f4_score: 74 },
  }),
}));

vi.mock('@/lib/hooks/use-fundamental', () => ({
  useFundamental: () => ({
    data: { f5_score: 77, f5_grade: 'WEAK' },
  }),
}));

describe('FrameworkScorePanel', () => {
  it('renders factor rows from the same F1-F5 scores shown in the detailed cards', async () => {
    render(
      <FrameworkScorePanel ticker="AAPL" onPreviewDetails={() => {}} regimeModifier={0} />,
    );

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
});
