import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { F2EarningsPanel } from '@/components/frameworks/f2-earnings-panel';

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
  return render(<F2EarningsPanel ticker="AAPL" />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('F2EarningsPanel', () => {
  it('renders the panel header with title', () => {
    renderPanel();
    expect(screen.getByText('F2 Earnings Quality')).toBeInTheDocument();
  });

  it('renders earnings data after earnings resolves', async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId('f2-content')).toBeInTheDocument();
    });

    // F2 score and grade are present
    expect(screen.getByTestId('f2-score')).toBeInTheDocument();
    expect(screen.getByTestId('f2-grade')).toHaveTextContent('STRONG BUY');

    // All five indicator cards are rendered
    expect(screen.getByTestId('f2-indicator-revenue-growth')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-eps-beats')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-guidance')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-backlog-visibility')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-margin-trajectory')).toBeInTheDocument();
  });

  it('displays revenue growth and guidance direction', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-content'));

    // Revenue growth value from mock: +65.0%
    expect(screen.getByText('+65.0%')).toBeInTheDocument();
    // Guidance direction from mock: guidance_label='RAISE_FULL_YEAR' → "Raised Full Year"
    expect(screen.getByText('Raised Full Year')).toBeInTheDocument();
  });
});
