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

  it('renders the backend action and display message', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    // Mock returns tier=TIER_2, action='GTC ADDS PERMITTED'
    expect(screen.getByTestId('regime-guidance-action-value')).toHaveTextContent(
      'GTC ADDS PERMITTED',
    );
    expect(screen.getByTestId('regime-guidance-output-text')).toHaveTextContent(
      'GTC adds permitted',
    );
  });

  it('does not render the regime war toggle', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.queryByTestId('regime-guidance-war-toggle')).not.toBeInTheDocument();
  });

  it('does not render the grey zone box for TIER_2', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.queryByTestId('regime-guidance-grey-zone-box')).not.toBeInTheDocument();
  });

  it('does not render exit rules note for TIER_2', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-guidance-content'));

    expect(screen.queryByTestId('regime-guidance-exit-rules-note')).not.toBeInTheDocument();
  });
});
