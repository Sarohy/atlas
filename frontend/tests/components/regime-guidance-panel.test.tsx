import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { RegimeGuidancePanel } from '@/components/frameworks/regime-guidance-panel';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderPanel(ticker = 'AAPL') {
  return render(<RegimeGuidancePanel ticker={ticker} />, { wrapper: createWrapper() });
}

describe('RegimeGuidancePanel', () => {
  it('renders the panel header', () => {
    renderPanel();

    expect(screen.getByText('Framework 3')).toBeInTheDocument();
  });

  it('does not render Brent or VIX values', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.queryByTestId('regime-guidance-brent')).not.toBeInTheDocument();
    expect(screen.queryByTestId('regime-guidance-vix')).not.toBeInTheDocument();
  });

  it('renders the backend action, conviction score, and instruction', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.getByTestId('regime-guidance-action-value')).toHaveTextContent('HOLD');
    expect(screen.getByTestId('regime-guidance-score')).toHaveTextContent('79');
    expect(screen.getByTestId('regime-guidance-output-text')).toHaveTextContent(
      'Hold position',
    );
  });

  it('does not render the regime war toggle', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.queryByTestId('regime-guidance-war-toggle')).not.toBeInTheDocument();
  });
});
