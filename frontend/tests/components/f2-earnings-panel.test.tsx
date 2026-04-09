import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
  return render(<F2EarningsPanel />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('F2EarningsPanel', () => {
  it('renders the panel header with title', () => {
    renderPanel();
    expect(screen.getByText('F2 Earnings Quality')).toBeInTheDocument();
  });

  it('shows tickers loading state while the portfolio is being fetched', () => {
    renderPanel();
    expect(screen.getByTestId('f2-tickers-loading')).toBeInTheDocument();
  });

  it('renders a ticker select populated from the backend', async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId('f2-ticker-select')).toBeInTheDocument();
    });

    expect(screen.getByRole('option', { name: 'AAPL' })).toBeInTheDocument();
  });

  it('renders earnings data after tickers and earnings both resolve', async () => {
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

  it('re-fetches when the user selects a different ticker', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-ticker-select'));

    const select = screen.getByTestId('f2-ticker-select');
    await userEvent.selectOptions(select, 'AAPL');

    expect((select as HTMLSelectElement).value).toBe('AAPL');
  });
});
