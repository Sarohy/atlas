import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Framework33Card } from '@/components/frameworks/framework33-card';
import { server } from '../mocks/server';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE = 'http://localhost:8000';

function makeLeapsResponse(overrides: Record<string, unknown> = {}) {
  return {
    ticker: 'MU',
    leaps_eligible: true,
    eligibility_undetermined: false,
    score: 88,
    tier: 'TIER_1',
    flow_confirmed: null,
    regime_state: 'CLEAR',
    regime_clears_leaps: true,
    gate_f7_active: false,
    gate_f29_passed: true,
    gate_f30_permits_leaps: true,
    iv_current: 0.45,
    iv_percentile: 0.55,
    iv_blocked: false,
    iv_alert: 'NONE',
    entry_conditions: [
      {
        condition_name: 'F33 Condition A — Calm Accumulation',
        status: 'CONFIRMED',
        met: true,
        detail: 'Calm Accumulation: drawdown=22.0% (≥20%) and VIX=16.5 in [15.0, 18.0]',
      },
      {
        condition_name: 'F33 Condition B — Washout',
        status: 'NOT_MET',
        met: false,
        detail: 'Not met: sector drawdown 10.0% < 25.0%',
      },
    ],
    conditions_met: 1,
    conditions_required: 1,
    block_reasons: [],
    warning_messages: [],
    data_age_minutes: 2,
    cache_hit: false,
    ...overrides,
  };
}

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderCard(ticker = 'MU') {
  return render(<Framework33Card ticker={ticker} />, {
    wrapper: createWrapper(),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Framework33Card', () => {
  it('renders the panel title "Framework 33"', () => {
    renderCard();
    expect(screen.getByText('Framework 33')).toBeInTheDocument();
  });

  it('renders the subtitle "LEAPS Entry Conditions V2"', () => {
    renderCard();
    expect(screen.getByText('LEAPS Entry Conditions V2')).toBeInTheDocument();
  });

  it('shows empty state when no ticker is provided', () => {
    renderCard('');
    expect(screen.getByTestId('f33-no-ticker')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    renderCard('MU');
    expect(screen.getByTestId('f33-loading')).toBeInTheDocument();
  });

  it('shows error state on API failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-error'));
    expect(screen.getByTestId('f33-error')).toBeInTheDocument();
  });

  it('renders Condition A card after data loads', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-condition-a'));
    expect(screen.getByTestId('f33-condition-a')).toBeInTheDocument();
  });

  it('renders Condition B card after data loads', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-condition-b'));
    expect(screen.getByTestId('f33-condition-b')).toBeInTheDocument();
  });

  it('shows CONFIRMED chip for Condition A when met=true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-condition-a-chip'));
    expect(screen.getByTestId('f33-condition-a-chip')).toHaveTextContent('CONFIRMED');
  });

  it('shows NOT MET chip for Condition B when met=false', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-condition-b-chip'));
    expect(screen.getByTestId('f33-condition-b-chip')).toHaveTextContent('NOT MET');
  });

  it('shows condition detail text', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-condition-a'));
    expect(
      screen.getByText(/Calm Accumulation: drawdown=22\.0%/),
    ).toBeInTheDocument();
  });

  it('shows ELIGIBLE chip when leaps_eligible=true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-entry-chip'));
    expect(screen.getByTestId('f33-entry-chip')).toHaveTextContent('ENTRY PERMITTED');
  });

  it('shows BLOCKED chip when leaps_eligible=false', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(
          makeLeapsResponse({
            leaps_eligible: false,
            block_reasons: ['F33 Condition A — Calm Accumulation not met'],
          }),
        ),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-entry-chip'));
    expect(screen.getByTestId('f33-entry-chip')).toHaveTextContent('BLOCKED');
  });

  it('shows size guidance section', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-size-guidance'));
    expect(screen.getByTestId('f33-size-guidance')).toBeInTheDocument();
  });

  it('shows carveout size cap when F30 gate state is unknown', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(
          makeLeapsResponse({ gate_f30_permits_leaps: null }),
        ),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-size-guidance'));
    // F30 unknown → conservative carveout 0.5%
    expect(screen.getByTestId('f33-size-guidance')).toHaveTextContent('0.5%');
  });

  it('shows standard 1.0% max when F30 permits LEAPS', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse({ gate_f30_permits_leaps: true })),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-size-guidance'));
    expect(screen.getByTestId('f33-size-guidance')).toHaveTextContent('1.0%');
  });

  it('shows excluded chip when ticker is in block_reasons with "excluded"', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(
          makeLeapsResponse({
            ticker: 'SIVE',
            leaps_eligible: false,
            entry_conditions: [],
            conditions_met: 0,
            block_reasons: ['SIVE is excluded from LEAPS (OTC / foreign / thin US options chain — see F33).'],
          }),
        ),
      ),
    );

    renderCard('SIVE');
    await waitFor(() => screen.getByTestId('f33-excluded-chip'));
    expect(screen.getByTestId('f33-excluded-chip')).toBeInTheDocument();
  });

  it('shows AND gate note section', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-and-gate-note'));
    expect(screen.getByTestId('f33-and-gate-note')).toBeInTheDocument();
  });

  it('renders the data age footer', async () => {
    server.use(
      http.get(`${BASE}/api/v1/leaps/eligibility/:ticker`, () =>
        HttpResponse.json(makeLeapsResponse()),
      ),
    );

    renderCard('MU');
    await waitFor(() => screen.getByTestId('f33-footer'));
    expect(screen.getByTestId('f33-footer')).toBeInTheDocument();
  });
});
