import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { Framework14Card } from '@/components/frameworks/framework14-card';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderCard(ticker = 'MU') {
  return render(<Framework14Card ticker={ticker} />, {
    wrapper: createWrapper(),
  });
}

// ---------------------------------------------------------------------------
// Tests — initial render
// ---------------------------------------------------------------------------

describe('Framework14Card', () => {
  it('renders the panel header with Framework 14 title', () => {
    renderCard();
    expect(screen.getByText('Framework 14')).toBeInTheDocument();
  });

  it('renders the subtitle "Position Sizing Rules"', () => {
    renderCard();
    expect(screen.getByText('Position Sizing Rules')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    renderCard();
    expect(screen.getByTestId('f14-loading')).toBeInTheDocument();
  });

  it('shows empty state when ticker is blank', () => {
    renderCard('');
    expect(screen.getByTestId('f14-empty')).toBeInTheDocument();
  });

  // ── After data resolves ──────────────────────────────────────────────────

  it('renders the status chip after data loads', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-status-chip'));
    expect(screen.getByTestId('f14-status-chip')).toBeInTheDocument();
  });

  it('shows GRANDFATHERED chip for MU mock data', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-status-chip'));
    expect(screen.getByTestId('f14-status-chip')).toHaveTextContent('GRANDFATHERED');
  });

  it('chip has blue tone class for GRANDFATHERED', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-status-chip'));
    expect(screen.getByTestId('f14-status-chip')).toHaveClass('is-f14-blue');
  });

  it('renders the 4-stat row after data loads', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-stats-row'));
    expect(screen.getByTestId('f14-stats-row')).toBeInTheDocument();
  });

  it('stat-weight shows position weight percentage', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-stat-weight'));
    expect(screen.getByTestId('f14-stat-weight')).toHaveTextContent('13.6%');
  });

  it('stat-adds shows NO when adds_permitted is false', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-stat-adds'));
    expect(screen.getByTestId('f14-stat-adds')).toHaveTextContent('NO');
  });

  it('stat-score-cap shows 85 when soft_cap_breached', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-stat-score-cap'));
    expect(screen.getByTestId('f14-stat-score-cap')).toHaveTextContent('85');
  });

  it('renders the concentration panel', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-conc-panel'));
    expect(screen.getByTestId('f14-conc-panel')).toBeInTheDocument();
  });

  it('soft cap badge shows YES when soft_cap_breached', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-soft-cap-badge'));
    expect(screen.getByTestId('f14-soft-cap-badge')).toHaveTextContent('YES');
  });

  it('hard review badge shows YES when hard_review_triggered', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-hard-review-badge'));
    expect(screen.getByTestId('f14-hard-review-badge')).toHaveTextContent('YES');
  });

  it('shows grandfathered expires-at when grandfathered', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-expires-at'));
    expect(screen.getByTestId('f14-expires-at')).toHaveTextContent('17.0%');
  });

  it('trim badge shows YES when trim_recommended', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-trim-badge'));
    expect(screen.getByTestId('f14-trim-badge')).toHaveTextContent('YES');
  });

  it('renders the weight bar section', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-weight-bar'));
    expect(screen.getByTestId('f14-weight-bar')).toBeInTheDocument();
  });

  it('weight bar fill has blue tone for GRANDFATHERED status', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-weight-bar-fill'));
    expect(screen.getByTestId('f14-weight-bar-fill')).toHaveClass('is-f14-blue');
  });

  it('renders the cluster panel with cluster name', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-cluster-name'));
    expect(screen.getByTestId('f14-cluster-name')).toHaveTextContent('AI Memory');
  });

  it('cluster status chip shows RED ZONE', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-cluster-status-chip'));
    expect(screen.getByTestId('f14-cluster-status-chip')).toHaveTextContent('RED ZONE');
  });

  it('cluster percentage shown in stat row', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-stat-cluster-weight'));
    expect(screen.getByTestId('f14-stat-cluster-weight')).toHaveTextContent('25.3%');
  });

  it('renders the sizing guidance box', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-guidance-box'));
    expect(screen.getByTestId('f14-guidance-box')).toBeInTheDocument();
  });

  it('sizing tier shows Core Anchor label', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-sizing-tier'));
    expect(screen.getByTestId('f14-sizing-tier')).toHaveTextContent('Core Anchor');
  });

  it('target range shows formatted min-max range', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-target-range'));
    expect(screen.getByTestId('f14-target-range')).toHaveTextContent('3.0%');
    expect(screen.getByTestId('f14-target-range')).toHaveTextContent('5.0%');
  });

  it('message is shown in guidance box', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-message'));
    expect(screen.getByTestId('f14-message').textContent?.length).toBeGreaterThan(0);
  });

  it('renders alerts section for grandfathered MU mock data', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f14-alerts'));
    expect(screen.getByTestId('f14-alerts')).toBeInTheDocument();
  });

  it('renders the card wrapper with correct data-testid', () => {
    renderCard('MU');
    expect(screen.getByTestId('framework14-card')).toBeInTheDocument();
  });
});
