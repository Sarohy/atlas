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
// Tests — header and toggles
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

  it('catalyst toggle changes aria-pressed when clicked', async () => {
    const user = userEvent.setup();
    renderPanel();

    const toggle = screen.getByTestId('tranche-catalyst-toggle');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('CATALYST: YES');
  });

  it('Iran toggle changes label when clicked', async () => {
    const user = userEvent.setup();
    renderPanel();

    const toggle = screen.getByTestId('tranche-iran-toggle');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('IRAN: CONFIRMED');
  });

  // ---------------------------------------------------------------------------
  // Tests — normal tranche display (cap inactive)
  // ---------------------------------------------------------------------------

  it('shows all four tranche rows when cap is not active', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-row-t1')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t2')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t3')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-row-t4')).toBeInTheDocument();
  });

  it('shows Waiting for T1 when catalyst is NO (default)', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t1')).toHaveTextContent('Waiting');
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

  it('T2 active when regimeRule is CAUTION after T1 confirmed', async () => {
    const user = userEvent.setup();
    renderPanel('AAPL', 'CAUTION');
    await waitFor(() => screen.getByTestId('tranche-content'));

    // T1 must fire first before T2 becomes eligible
    await user.click(screen.getByTestId('tranche-catalyst-toggle'));

    await waitFor(() => {
      expect(screen.getByTestId('tranche-value-t2')).toHaveTextContent(
        '20-25% of available cash',
      );
    });
  });

  it('T2 blocked when regimeRule is NORMAL', async () => {
    renderPanel('AAPL', 'NORMAL');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t2')).toHaveTextContent('Blocked');
  });

  it('T3 blocked when regimeRule is CLEAR but AND gate not passed (default 0/5)', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-content'));

    // Mock returns 0 signals confirmed by default -> gate blocked -> T3 Blocked
    expect(screen.getByTestId('tranche-value-t3')).toHaveTextContent('Blocked');
  });

  it('T4 active after toggling Iran resolution to confirmed and T1 to yes', async () => {
    const user = userEvent.setup();
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    // T1 must fire first
    await user.click(screen.getByTestId('tranche-catalyst-toggle'));
    // Then confirm Iran resolution
    await user.click(screen.getByTestId('tranche-iran-toggle'));

    await waitFor(() => {
      expect(screen.getByTestId('tranche-value-t4')).toHaveTextContent(
        'Remaining cash to floor',
      );
    });
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

  // ---------------------------------------------------------------------------
  // Tests — sequential gate display (T1 not fired → WAITING / Requires T1 first)
  // ---------------------------------------------------------------------------

  it('T1 row shows Waiting chip when catalyst is NO (T1 not fired)', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-value-t1')).toHaveTextContent('Waiting');
  });

  it('T2 shows Requires T1 first reason when T1 not fired', async () => {
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-seq-reason-t2')).toBeInTheDocument();
    expect(screen.getByTestId('tranche-seq-reason-t2')).toHaveTextContent(
      'Requires T1 first',
    );
  });

  it('T2/T3/T4 seq reason not shown after T1 fires', async () => {
    const user = userEvent.setup();
    renderPanel();
    await waitFor(() => screen.getByTestId('tranche-content'));

    await user.click(screen.getByTestId('tranche-catalyst-toggle'));

    await waitFor(() => {
      expect(screen.queryByTestId('tranche-seq-reason-t2')).not.toBeInTheDocument();
      expect(screen.queryByTestId('tranche-seq-reason-t3')).not.toBeInTheDocument();
      expect(screen.queryByTestId('tranche-seq-reason-t4')).not.toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Tests — concentration cap suppression (Change 3)
  // ---------------------------------------------------------------------------

  it('shows cap box and hides tranche rows when ticker is MU (cap active)', async () => {
    renderPanel('MU', 'NORMAL');
    await waitFor(() => screen.getByTestId('tranche-cap-box'));

    expect(screen.getByTestId('tranche-cap-box')).toBeInTheDocument();
    expect(screen.queryByTestId('tranche-row-t1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tranche-row-t2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tranche-row-t3')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tranche-row-t4')).not.toBeInTheDocument();
  });

  it('cap box shows suppression message when cap active', async () => {
    renderPanel('TSM', 'NORMAL');
    await waitFor(() => screen.getByTestId('tranche-cap-box'));

    const capBox = screen.getByTestId('tranche-cap-box');
    expect(capBox).toHaveTextContent(/concentration cap/i);
  });

  it('cap box shows current position weight when cap active', async () => {
    renderPanel('MU', 'NORMAL');
    await waitFor(() => screen.getByTestId('tranche-cap-weight'));

    // MU mock returns position_weight=0.136 -> displays as "13.6%"
    expect(screen.getByTestId('tranche-cap-weight')).toHaveTextContent('13.6%');
  });

  it('hides the regime badge when cap is active', async () => {
    renderPanel('MU', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-cap-box'));

    expect(screen.queryByTestId('tranche-regime-badge')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Tests — AND gate section (Change 1)
  // ---------------------------------------------------------------------------

  it('does not show AND gate section when regime is not CLEAR', async () => {
    renderPanel('AAPL', 'CAUTION');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.queryByTestId('tranche-and-gate')).not.toBeInTheDocument();
  });

  it('shows AND gate section when regime is CLEAR', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.getByTestId('tranche-and-gate')).toBeInTheDocument();
  });

  it('AND gate section shows BLOCKED status when signals < 3', async () => {
    // Default mock returns 0/5 signals for AAPL CLEAR
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-and-gate-status'));

    expect(screen.getByTestId('tranche-and-gate-status')).toHaveTextContent('BLOCKED');
  });

  it('AND gate section shows 5 signal slots', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-and-gate'));

    // 5 signal name spans
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByTestId(`tranche-signal-name-${i}`)).toBeInTheDocument();
    }
  });

  it('shows signals confirmed count in AND gate section', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-signals-confirmed'));

    expect(screen.getByTestId('tranche-signals-confirmed')).toHaveTextContent('0 of 5');
  });

  // ---------------------------------------------------------------------------
  // Tests — T3 waiting notice (Change 1)
  // ---------------------------------------------------------------------------

  it('shows T3 waiting notice when CLEAR but gate blocked', async () => {
    renderPanel('AAPL', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-t3-waiting'));

    expect(screen.getByTestId('tranche-t3-waiting')).toBeInTheDocument();
  });

  it('T3 waiting notice not shown when regime is not CLEAR', async () => {
    renderPanel('AAPL', 'CAUTION');
    await waitFor(() => screen.getByTestId('tranche-content'));

    expect(screen.queryByTestId('tranche-t3-waiting')).not.toBeInTheDocument();
  });

  it('T3 waiting notice not shown when cap is active', async () => {
    renderPanel('MU', 'CLEAR');
    await waitFor(() => screen.getByTestId('tranche-cap-box'));

    expect(screen.queryByTestId('tranche-t3-waiting')).not.toBeInTheDocument();
  });
});

