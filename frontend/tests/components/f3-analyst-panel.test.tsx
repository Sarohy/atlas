import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { F3AnalystPanel } from '@/components/frameworks/f3-analyst-panel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderPanel() {
  return render(<F3AnalystPanel ticker="AAPL" />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('F3AnalystPanel', () => {
  it('renders the panel header with title', () => {
    renderPanel();
    expect(screen.getByText('F3 Analyst Conviction')).toBeInTheDocument();
  });

  it('renders analyst data after analyst resolves', async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId('f3-content')).toBeInTheDocument();
    });

    // F3 score and grade are present
    expect(screen.getByTestId('f3-score')).toBeInTheDocument();
    expect(screen.getByTestId('f3-grade')).toHaveTextContent('STRONG BUY');

    // All five indicator cards are rendered
    expect(screen.getByTestId('f3-indicator-consensus-rating')).toBeInTheDocument();
    expect(screen.getByTestId('f3-indicator-pt-upside')).toBeInTheDocument();
    expect(screen.getByTestId('f3-indicator-pt-direction')).toBeInTheDocument();
    expect(screen.getByTestId('f3-indicator-analyst-coverage')).toBeInTheDocument();
    expect(screen.getByTestId('f3-indicator-recent-upgrades')).toBeInTheDocument();
  });

  it('displays consensus label and upside from mock data', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f3-content'));

    // Consensus label from mock: STRONG BUY
    expect(screen.getByTestId('f3-consensus-label')).toHaveTextContent('STRONG BUY');
    // PT upside from mock: 26.0%
    expect(screen.getByText('+26.0%')).toBeInTheDocument();
  });
});
