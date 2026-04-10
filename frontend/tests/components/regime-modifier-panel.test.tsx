import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { RegimeModifierPanel } from '@/components/frameworks/regime-modifier-panel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderPanel(ticker = 'AAPL') {
  return render(<RegimeModifierPanel ticker={ticker} />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RegimeModifierPanel', () => {
  it('renders the panel header', () => {
    renderPanel();
    expect(screen.getByText('Framework 2')).toBeInTheDocument();
  });

  it('renders the war zone toggle button', () => {
    renderPanel();
    const toggle = screen.getByTestId('regime-war-toggle');
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    expect(toggle).toHaveTextContent('WAR ZONE');
  });

  it('shows loading state while fetching', () => {
    renderPanel();
    expect(screen.getByTestId('regime-loading')).toBeInTheDocument();
  });

  it('renders regime content after data resolves', async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId('regime-content')).toBeInTheDocument();
    });
  });

  it('displays Brent crude price', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-brent')).toBeInTheDocument();
    expect(screen.getByTestId('regime-brent')).toHaveTextContent('$97.50');
  });

  it('displays VIX value', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-vix')).toHaveTextContent('27.30');
  });

  it('displays the triggered rule badge', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-rule-badge')).toHaveTextContent('RULE 2 — CAUTION');
  });

  it('shows the score delta label', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-delta')).toHaveTextContent('−5 pts');
  });

  it('displays base score and adjusted score', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-base-score')).toHaveTextContent('79');
    expect(screen.getByTestId('regime-adjusted-score')).toHaveTextContent('74');
  });

  it('shows cash guidance when a rule is triggered', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-cash-block')).toBeInTheDocument();
    expect(screen.getByTestId('regime-cash-pct')).toHaveTextContent('25%');
    expect(screen.getByTestId('regime-cash-pct')).toHaveTextContent('35%');
  });

  it('shows USD cash guidance when ticker position value is available', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-cash-usd')).toHaveTextContent('$25,000');
    expect(screen.getByTestId('regime-cash-usd')).toHaveTextContent('$35,000');
  });

  it('shows output text instruction', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('regime-content'));

    expect(screen.getByTestId('regime-output-text')).toHaveTextContent('must stay in cash');
  });

  it('toggling war flag changes button state to active', async () => {
    const user = userEvent.setup();
    renderPanel();

    const toggle = screen.getByTestId('regime-war-toggle');
    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('WAR ACTIVE');
  });

  it('shows WAR ACTIVE badge in market row when war is on', async () => {
    const user = userEvent.setup();
    renderPanel();

    // Toggle war on, then wait for the refetch to settle
    await user.click(screen.getByTestId('regime-war-toggle'));

    await waitFor(() => {
      expect(screen.getByTestId('regime-war-badge')).toBeInTheDocument();
    });
  });

  it('does not fetch when ticker is empty', () => {
    renderPanel('');
    // Loading state should not appear because query is disabled
    expect(screen.queryByTestId('regime-loading')).not.toBeInTheDocument();
  });
});
