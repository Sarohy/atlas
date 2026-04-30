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
    expect(screen.getByTestId('f2-grade')).toHaveTextContent('STRONG');

    // All five sub-factor cards are rendered (v7.3.4)
    expect(screen.getByTestId('f2-indicator-revenue-growth')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-gross-margin-trend')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-eps-consistency')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-guidance-reliability')).toBeInTheDocument();
    expect(screen.getByTestId('f2-indicator-forward-visibility')).toBeInTheDocument();
  });

  it('displays revenue growth YoY from mock data', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-content'));

    // Revenue growth value from mock: +65.0%
    expect(screen.getByText('+65.0%')).toBeInTheDocument();
  });

  it('shows DATA GAP badge for guidance when sf4_data_gap is true', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-content'));

    // Mock has sf4_data_gap: true
    expect(screen.getByTestId('f2-sf4-data-gap')).toBeInTheDocument();
  });

  it('shows DATA GAP amber flag badge when data_gap_applied is true', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-content'));

    // Mock has data_gap_applied: true
    expect(screen.getByTestId('f2-flag-data-gap')).toBeInTheDocument();
  });

  it('shows forward visibility label from mock data', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f2-content'));

    // Mock has sf5_forward_visibility_label: 'SPECIFIC_RAISED'
    expect(screen.getByText('Guidance Raised')).toBeInTheDocument();
  });
});
