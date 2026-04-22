import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { Framework13Card } from '@/components/frameworks/framework13-card';

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
  return render(<Framework13Card ticker={ticker} />, {
    wrapper: createWrapper(),
  });
}

// ---------------------------------------------------------------------------
// Tests — initial render
// ---------------------------------------------------------------------------

describe('Framework13Card', () => {
  it('renders the panel header with Framework 13 title', () => {
    renderCard();
    expect(screen.getByText('Framework 13')).toBeInTheDocument();
  });

  it('renders the subtitle "Beta Management"', () => {
    renderCard();
    expect(screen.getByText('Beta Management')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    renderCard();
    expect(screen.getByTestId('f13-loading')).toBeInTheDocument();
  });

  it('shows empty state when ticker is blank', () => {
    renderCard('');
    expect(screen.getByTestId('f13-empty')).toBeInTheDocument();
  });

  // ── After data resolves ──────────────────────────────────────────────────

  it('renders the status chip after data loads', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-status-chip'));
    expect(screen.getByTestId('f13-status-chip')).toBeInTheDocument();
  });

  it('shows NORMAL chip for MU mock data at 1% weight (no cap)', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-status-chip'));
    expect(screen.getByTestId('f13-status-chip')).toHaveTextContent('NORMAL');
  });

  it('chip has grey tone class for NORMAL', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-status-chip'));
    expect(screen.getByTestId('f13-status-chip')).toHaveClass('is-f13-grey');
  });

  it('renders the 4-stat row after data loads', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-stats-row'));
    expect(screen.getByTestId('f13-stats-row')).toBeInTheDocument();
  });

  it('stat-beta shows MU beta value', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-stat-beta'));
    expect(screen.getByTestId('f13-stat-beta')).toHaveTextContent('1.65');
  });

  it('stat-adds shows YES for uncapped position', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-stat-adds'));
    expect(screen.getByTestId('f13-stat-adds')).toHaveTextContent('YES');
  });

  it('renders the beta bar section', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-beta-bar'));
    expect(screen.getByTestId('f13-beta-bar')).toBeInTheDocument();
  });

  it('renders the exposure note', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-exposure-note'));
    expect(screen.getByTestId('f13-exposure-note')).toBeInTheDocument();
  });

  it('renders the sizing tier panel', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-tier-panel'));
    expect(screen.getByTestId('f13-tier-panel')).toBeInTheDocument();
  });

  it('shows HIGH_BETA tier for MU', async () => {
    renderCard('MU');
    await waitFor(() => screen.getByTestId('f13-sizing-tier'));
    expect(screen.getByTestId('f13-sizing-tier')).toHaveTextContent('High Beta (1.5-2.0)');
  });

  // ── Error state ──────────────────────────────────────────────────────────

  it('shows error message when fetch fails', async () => {
    const { server } = await import('../mocks/server');
    const { http, HttpResponse } = await import('msw');

    server.use(
      http.get('*/api/v1/framework13/ERR_TICKER', () =>
        HttpResponse.json({ detail: 'Internal server error' }, { status: 500 }),
      ),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    render(<Framework13Card ticker="ERR_TICKER" />, { wrapper: Wrapper });
    await waitFor(() => screen.getByTestId('f13-error'), { timeout: 3000 });
    expect(screen.getByTestId('f13-error')).toBeInTheDocument();
  });

  // ── Adds = NO when capped (AAOI above cap) ───────────────────────────────

  it('shows NO for adds when AAOI is capped', async () => {
    // MSW mock returns beta_cap_active: true for position > 1% (AAOI cap = 1%)
    // The mock uses position_weight_override; default is 0.01 which equals cap
    // exactly. For this test we trust the mock returns adds_permitted: false
    // when cap is active (position_weight_override=0.02, 2% > 1% cap).
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { server } = await import('../mocks/server');
    const { http, HttpResponse } = await import('msw');
    server.use(
      http.get('*/api/v1/framework13/AAOI', () =>
        HttpResponse.json({
          ticker: 'AAOI',
          beta: 3.30,
          beta_source: 'CONFIRMED',
          position_weight_pct: 2.0,
          position_dollars: 0,
          effective_exposure_pct: 6.6,
          effective_exposure_note: '2.0% position × beta 3.3 = 6.60% effective exposure',
          beta_cap_active: true,
          beta_cap_limit_pct: 1.0,
          beta_cap_reason: 'Beta 3.3 — hard cap at 1.0%',
          sizing_tier: 'AAOI_TYPE_HIGH_BETA',
          max_weight_pct: 1.0,
          adds_permitted: false,
          warning_level: 'RED',
          warning_message: 'Beta cap active — max 1.0% NAV',
          beta_source_flag: false,
        }),
      ),
    );

    render(<Framework13Card ticker="AAOI" />, { wrapper: Wrapper });
    await waitFor(() => screen.getByTestId('f13-stat-adds'));
    expect(screen.getByTestId('f13-stat-adds')).toHaveTextContent('NO');
  });

  it('shows CAPPED chip when beta_cap_active', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { server } = await import('../mocks/server');
    const { http, HttpResponse } = await import('msw');
    server.use(
      http.get('*/api/v1/framework13/CRDO', () =>
        HttpResponse.json({
          ticker: 'CRDO',
          beta: 2.67,
          beta_source: 'CONFIRMED',
          position_weight_pct: 1.5,
          position_dollars: 0,
          effective_exposure_pct: 4.0,
          effective_exposure_note: '1.5% position × beta 2.67 = 4.00% effective exposure',
          beta_cap_active: true,
          beta_cap_limit_pct: 1.0,
          beta_cap_reason: 'Beta 2.67 — high beta cap at 1.0%',
          sizing_tier: 'VERY_HIGH_BETA',
          max_weight_pct: 1.0,
          adds_permitted: false,
          warning_level: 'RED',
          warning_message: 'Beta cap active — max 1.0% NAV',
          beta_source_flag: false,
        }),
      ),
    );

    render(<Framework13Card ticker="CRDO" />, { wrapper: Wrapper });
    await waitFor(() => screen.getByTestId('f13-status-chip'));
    expect(screen.getByTestId('f13-status-chip')).toHaveTextContent('CAPPED');
  });
});
