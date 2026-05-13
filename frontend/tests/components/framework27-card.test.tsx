import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Framework27Card } from '@/components/frameworks/framework27-card';
import { server } from '../mocks/server';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE = 'http://localhost:8000';

function makeContagionResponse(overrides: Record<string, unknown> = {}) {
  return {
    f17_active: false,
    rules_evaluated: 3,
    rules_triggered: 0,
    triggered_rules: [],
    all_rules: [
      {
        rule_id: 1,
        ticker: 'MU',
        primary_risk: 'DRAM supply disruption',
        secondary_exposure: 'NAND flash overhang',
        contagion_trigger_type: 'ASIA_FREIGHT_DISRUPTION_PCT',
        trigger_condition: 'Asia freight index > 120% of 90-day MA',
        triggered: false,
        trigger_reason: 'Asia freight index at 98% — below threshold',
        action_on_trigger: 'Reduce MU position to 6% NAV',
      },
      {
        rule_id: 2,
        ticker: 'MRVL',
        primary_risk: 'Copper and indium shortage',
        secondary_exposure: 'PCB layer cost spike',
        contagion_trigger_type: 'METALS_DISRUPTION',
        trigger_condition: 'Indium spot > $250/kg',
        triggered: false,
        trigger_reason: 'Indium spot at $190/kg — below threshold',
        action_on_trigger: 'Flag for review; hold sizing',
      },
      {
        rule_id: 3,
        ticker: 'NVDA',
        primary_risk: 'GPU substrate shortage',
        secondary_exposure: 'CoWoS advanced packaging lead time',
        contagion_trigger_type: 'INDIUM_SUPPLY_DISRUPTION',
        trigger_condition: 'Operator confirms indium disruption',
        triggered: false,
        trigger_reason: '',
        action_on_trigger: 'Pause new NVDA buys',
      },
    ],
    asia_freight_flagged: false,
    metals_disruption_flagged: false,
    indium_disruption_flagged: false,
    brent_price: 82.5,
    conflict_duration_days: 14,
    cache_hit: false,
    data_as_of: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderCard() {
  return render(<Framework27Card />, { wrapper: createWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Framework27Card', () => {
  // ── Static header ────────────────────────────────────────────────────────

  it('renders the "FRAMEWORK 27" label', () => {
    renderCard();
    expect(screen.getByText('FRAMEWORK 27')).toBeInTheDocument();
  });

  it('renders the subtitle "Supply Chain Contagion Map"', () => {
    renderCard();
    expect(screen.getByText('Supply Chain Contagion Map')).toBeInTheDocument();
  });

  // ── Loading state ────────────────────────────────────────────────────────

  it('shows loading state while data is fetching', () => {
    renderCard();
    expect(screen.getByTestId('f27-loading')).toBeInTheDocument();
  });

  // ── Error state ──────────────────────────────────────────────────────────

  it('shows error state on API failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 }),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-error'));
    expect(screen.getByTestId('f27-error')).toBeInTheDocument();
  });

  // ── Data loaded ──────────────────────────────────────────────────────────

  it('shows the rules count after data loads', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-rules-count'));
    expect(screen.getByTestId('f27-rules-count')).toHaveTextContent('0 / 3');
  });

  it('shows CLEAR status chip when no rules triggered', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-status-chip'));
    expect(screen.getByTestId('f27-status-chip')).toHaveTextContent('CLEAR');
  });

  it('shows TRIGGERED status chip when rules fired', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(
          makeContagionResponse({
            rules_triggered: 1,
            triggered_rules: [
              makeContagionResponse().all_rules[0],
            ],
          }),
        ),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-status-chip'));
    expect(screen.getByTestId('f27-status-chip')).toHaveTextContent('TRIGGERED');
  });

  it('renders all rule rows after data loads', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-rules-table'));
    const rows = screen.getAllByTestId(/^f27-rule-row-/);
    expect(rows).toHaveLength(3);
  });

  it('shows ticker symbol in rule rows', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-rules-table'));
    expect(screen.getByTestId('f27-rule-row-1')).toHaveTextContent('MU');
  });

  it('shows brent price from F17 context', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-brent-price'));
    expect(screen.getByTestId('f27-brent-price')).toHaveTextContent('$82.50');
  });

  it('shows operator flags panel', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-operator-flags'));
    expect(screen.getByTestId('f27-operator-flags')).toBeInTheDocument();
  });

  it('shows asia freight flag as inactive when not flagged', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-flag-asia'));
    expect(screen.getByTestId('f27-flag-asia')).not.toHaveClass('is-f27-flag-active');
  });

  it('shows asia freight flag as active when flagged', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse({ asia_freight_flagged: true })),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-flag-asia'));
    expect(screen.getByTestId('f27-flag-asia')).toHaveClass('is-f27-flag-active');
  });

  it('renders the "Add Manual Flag" button', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-open-flag-form'));
    expect(screen.getByTestId('f27-open-flag-form')).toBeInTheDocument();
  });

  it('shows the manual flag form when the button is clicked', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse()),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-open-flag-form'));
    await userEvent.click(screen.getByTestId('f27-open-flag-form'));
    expect(screen.getByTestId('f27-flag-form')).toBeInTheDocument();
  });

  it('shows a cache badge when cache_hit is true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse({ cache_hit: true })),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-cache-badge'));
    expect(screen.getByTestId('f27-cache-badge')).toBeInTheDocument();
  });

  it('does not show cache badge when cache_hit is false', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse({ cache_hit: false })),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-rules-table'));
    expect(screen.queryByTestId('f27-cache-badge')).not.toBeInTheDocument();
  });

  it('shows F17 active badge when geopolitical flag is active', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse({ f17_active: true })),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-f17-badge'));
    expect(screen.getByTestId('f27-f17-badge')).toHaveClass('is-f27-f17-active');
  });

  it('shows F17 inactive badge when geopolitical flag is not active', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework27/contagion`, () =>
        HttpResponse.json(makeContagionResponse({ f17_active: false })),
      ),
    );

    renderCard();
    await waitFor(() => screen.getByTestId('f27-f17-badge'));
    expect(screen.getByTestId('f27-f17-badge')).not.toHaveClass('is-f27-f17-active');
  });
});
