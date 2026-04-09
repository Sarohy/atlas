import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { F1MomentumPanel } from '@/components/frameworks/f1-momentum-panel';

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
  return render(<F1MomentumPanel ticker="AAPL" />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('F1MomentumPanel', () => {
  it('renders the panel header with title', () => {
    renderPanel();
    expect(screen.getByText('F1 Momentum')).toBeInTheDocument();
  });

  it('renders momentum data after momentum resolves', async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId('f1-content')).toBeInTheDocument();
    });

    // F1 score and grade are present
    expect(screen.getByTestId('f1-score')).toBeInTheDocument();
    expect(screen.getByTestId('f1-grade')).toHaveTextContent('STRONG BUY');

    // All six indicator cards are rendered
    expect(screen.getByTestId('f1-indicator-rsi')).toBeInTheDocument();
    expect(screen.getByTestId('f1-indicator-macd')).toBeInTheDocument();
    expect(screen.getByTestId('f1-indicator-ma-alignment')).toBeInTheDocument();
    expect(screen.getByTestId('f1-indicator-52-week-position')).toBeInTheDocument();
    expect(screen.getByTestId('f1-indicator-performance')).toBeInTheDocument();
    expect(screen.getByTestId('f1-indicator-sector-momentum')).toBeInTheDocument();
  });

  it('displays RSI value and MA alignment label', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('f1-content'));

    expect(screen.getByText('62.5')).toBeInTheDocument();
    expect(screen.getByText('ABOVE ALL')).toBeInTheDocument();
  });
});
