import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { TrancheSizingPanel } from '@/components/frameworks/tranche-sizing-panel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderPanel(ticker = 'AAPL', regimeRule = 'NORMAL') {
  return render(<TrancheSizingPanel ticker={ticker} regimeRule={regimeRule} />, {
    wrapper: createWrapper(),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TrancheSizingPanel', () => {
  it('renders the panel header with Framework 4 title', () => {
    renderPanel();
    expect(screen.getByText('Framework 4')).toBeInTheDocument();
  });

  it('renders the catalyst toggle defaulting to NO', () => {
    renderPanel();
    const toggle = screen.getByTestId('tranche-catalyst-toggle');
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    expect(toggle).toHaveTextContent('CATALYST: NO');
  });

  it('renders the Iran resolution toggle defaulting to PENDING', () => {
    renderPanel();
    const toggle = screen.getByTestId('tranche-iran-toggle');
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    expect(toggle).toHaveTextContent('IRAN: PENDING');
  });

  it('shows loading state initially', () => {
    renderPanel();
    expect(screen.getByTestId('tranche-loading')).toBeInTheDocument();
  });

  it('renders tranche content after data resolves', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));
    expect(screen.getByTestId('tranche-content')).toBeInTheDocument();
  });

  it('shows all four tranche rows', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-row-t1')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t2')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t3')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t4')).toBeInTheDocument();
  });

  it('shows Blocked for T1 when catalyst is NO (default)', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t1')).toHaveTextContent('Blocked');
  });

  it('shows T1 active after toggling catalyst to YES', async () => {
    const user = userEvent.setup();
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    await user.click(screen.getByTestId('tranche-catalyst-toggle'));

    await waitFor(() => {
      expect(screen.getByTestId('tranche-value-t1')).toHaveTextContent(
        '10-15% of available cash',
      );
    });
  });

  it('catalyst toggle changes aria-pressed when clicked', async () => {
    const user = userEvent.setup();
    renderPanel();

    const toggle = screen.getByTestId('tranche-catalyst-toggle');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('CATALYST: YES');
  });

  it('T2 active when regimeRule is CAUTION', async () => {
    renderPanel('AAPL', 'CAUTION');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t2')).toHaveTextContent(
      '20-25% of available cash',
    );
  });

  it('T2 blocked when regimeRule is NORMAL', async () => {
    renderPanel('AAPL', 'NORMAL');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t2')).toHaveTextContent('Blocked');
  });

  it('T3 active when regimeRule is CLEAR', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t3')).toHaveTextContent(
      '30-40% of available cash',
    );
  });

  it('T4 active after toggling Iran resolution to confirmed', async () => {
    const user = userEvent.setup();
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    await user.click(screen.getByTestId('tranche-iran-toggle'));

    await waitFor(() => {
      expect(screen.getByTestId('tranche-value-t4')).toHaveTextContent(
        'Remaining cash to floor',
      );
    });
  });

  it('Iran toggle changes label when clicked', async () => {
    const user = userEvent.setup();
    renderPanel();

    const toggle = screen.getByTestId('tranche-iran-toggle');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('IRAN: CONFIRMED');
  });

  it('displays the regime badge with the injected regimeRule', async () => {
    renderPanel('AAPL', 'CAUTION');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-regime-badge')).toHaveTextContent('REGIME: CAUTION');
  });

  it('does not render Brent or VIX values', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.queryByTestId('regime-brent')).not.toBeInTheDocument();
    expect(screen.queryByTestId('regime-vix')).not.toBeInTheDocument();
  });
});
