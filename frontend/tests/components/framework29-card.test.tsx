import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Framework29Card } from '@/components/frameworks/framework29-card';
import { server } from '../mocks/server';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE = 'http://localhost:8000';
const TEST_TICKER = 'MU';

function makeF29Evaluation(overrides: Record<string, unknown> = {}) {
  return {
    framework_id: 29,
    ticker: TEST_TICKER,
    gate_status: 'BLOCKED',
    entry_type: 'DISCRETIONARY',
    regime_precondition: {
      regime: 'CAUTION',
      passed: true,
      reason: null,
      regime_undefined_flag: false,
    },
    washout_evaluation: {
      matched: false,
      session_change_pct: -0.02,
      f4_score: 15.0,
      conditions: [
        { id: 'washout_price_drop', met: false, value: -2.0, reason: 'Required: ≤-8%' },
        { id: 'washout_f4_score', met: true, value: 15.0, reason: 'Required: ≥11' },
      ],
      data_gaps: [],
    },
    catalyst_validated_evaluation: {
      matched: false,
      position_held: true,
      score_tier_pass: true,
      sub_conditions: [
        { id: 'catalyst_13f_concentration_buy', met: 'UNAVAILABLE', value: null, reason: '13F_FEED_NOT_WIRED: 13F concentration buy data source not yet integrated' },
        { id: 'catalyst_analyst_pt_raise', met: 'UNAVAILABLE', value: null, reason: 'ANALYST_FEED_PENDING_SUBSCRIPTION: Analyst PT raise + management meeting linkage requires a feed not yet subscribed' },
        { id: 'catalyst_revenue_inflection', met: 'UNAVAILABLE', value: null, reason: 'EARNINGS_FEED_NOT_WIRED: Earnings revenue inflection data unavailable' },
      ],
      sub_conditions_met_count: 0,
      data_gaps: [
        '13F_FEED_NOT_WIRED: 13F concentration buy data source not yet integrated',
        'ANALYST_FEED_PENDING_SUBSCRIPTION: Analyst PT raise + management meeting linkage requires a feed not yet subscribed',
        'EARNINGS_FEED_NOT_WIRED: Earnings revenue inflection data unavailable',
      ],
    },
    discretionary_evaluation: {
      signals: [
        { id: 'disc_s1_vix', label: 'VIX touches regime-high (10-session) then declines 3 consecutive', met: false, value: 17.92 },
        { id: 'disc_s3_pcr', label: 'Put/call ratio spikes ≥1.3 then reverses ≥0.15 from peak', met: false, value: 0.47 },
        { id: 'disc_s4_breadth', label: 'S&P 500 breadth dips ≤30% (10-session) then recovers ≥35%', met: false, value: 44.76 },
      ],
      signals_met: 0,
      signals_unavailable: 0,
      threshold: 2,
      threshold_inferred: true,
    },
    decision_trace_id: 'test-trace-id-001',
    evaluated_at: '2026-05-14T13:54:31Z',
    all_data_gaps: [
      '13F_FEED_NOT_WIRED: 13F concentration buy data source not yet integrated',
      'ANALYST_FEED_PENDING_SUBSCRIPTION: Analyst PT raise + management meeting linkage requires a feed not yet subscribed',
    ],
    ...overrides,
  };
}

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderCard(ticker = TEST_TICKER) {
  return render(<Framework29Card ticker={ticker} />, { wrapper: createWrapper() });
}

function mockEvaluationEndpoint(response: Record<string, unknown> = makeF29Evaluation()) {
  server.use(
    http.get(`${BASE}/api/v1/framework29/evaluate/${TEST_TICKER}`, () =>
      HttpResponse.json(response),
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Framework29Card — three-path classifier', () => {
  it('renders placeholder when no ticker provided', () => {
    renderCard('');
    expect(screen.getByTestId('f29-no-ticker')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    server.use(
      http.get(`${BASE}/api/v1/framework29/evaluate/${TEST_TICKER}`, async () => {
        await new Promise(() => {}); // never resolves
      }),
    );
    renderCard();
    expect(screen.getByTestId('f29-loading')).toBeInTheDocument();
  });

  it('renders ticker badge in header', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-ticker-badge')).toBeInTheDocument());
    expect(screen.getByTestId('f29-ticker-badge')).toHaveTextContent(TEST_TICKER);
  });

  it('renders gate status chip with correct label', async () => {
    mockEvaluationEndpoint(makeF29Evaluation({ gate_status: 'PASS', entry_type: 'WASHOUT' }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-gate-chip')).toBeInTheDocument());
    expect(screen.getByTestId('f29-gate-chip')).toHaveTextContent('LEAPS PERMITTED');
  });

  it('renders BLOCKED gate chip when gate is blocked', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-gate-chip')).toBeInTheDocument());
    expect(screen.getByTestId('f29-gate-chip')).toHaveTextContent('LEAPS BLOCKED');
  });

  it('renders UNAVAILABLE gate chip with amber styling', async () => {
    mockEvaluationEndpoint(
      makeF29Evaluation({
        gate_status: 'UNAVAILABLE',
        entry_type: 'UNAVAILABLE',
        regime_precondition: {
          regime: 'PRE_CATALYST',
          passed: false,
          reason: "Regime 'PRE_CATALYST' is not in the permitted regime taxonomy",
          regime_undefined_flag: true,
        },
      }),
    );
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-gate-chip')).toBeInTheDocument());
    expect(screen.getByTestId('f29-gate-chip')).toHaveTextContent('DATA UNAVAILABLE');
  });

  it('renders regime precondition card', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-regime-precondition')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('f29-regime-chip')).toHaveTextContent('CAUTION');
  });

  it('shows REGIME_UNDEFINED badge for unknown regimes', async () => {
    mockEvaluationEndpoint(
      makeF29Evaluation({
        gate_status: 'UNAVAILABLE',
        entry_type: 'UNAVAILABLE',
        regime_precondition: {
          regime: 'PRE_CATALYST',
          passed: false,
          reason: "Regime 'PRE_CATALYST' is not in the permitted regime taxonomy",
          regime_undefined_flag: true,
        },
      }),
    );
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-regime-undefined-badge')).toBeInTheDocument(),
    );
  });

  it('renders washout path card', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-washout-detail')).toBeInTheDocument());
    expect(screen.getByTestId('f29-washout-matched')).toHaveTextContent('NOT MATCHED');
  });

  it('renders catalyst validated path card', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-catalyst-detail')).toBeInTheDocument());
    expect(screen.getByTestId('f29-catalyst-matched')).toHaveTextContent('NOT MATCHED');
  });

  it('renders position_held status in catalyst card', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-catalyst-position-held')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('f29-catalyst-position-held')).toHaveTextContent('MET');
  });

  it('shows sub-conditions count in catalyst card', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-catalyst-sub-count')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('f29-catalyst-sub-count')).toHaveTextContent('0 / 3');
  });

  it('renders discretionary path when entry_type is DISCRETIONARY', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-discretionary-detail')).toBeInTheDocument(),
    );
  });

  it('does NOT render discretionary path when entry_type is WASHOUT', async () => {
    mockEvaluationEndpoint(
      makeF29Evaluation({
        gate_status: 'PASS',
        entry_type: 'WASHOUT',
        discretionary_evaluation: null,
      }),
    );
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-washout-detail')).toBeInTheDocument());
    expect(screen.queryByTestId('f29-discretionary-detail')).not.toBeInTheDocument();
  });

  it('renders THRESHOLD_INFERRED badge in discretionary path', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId('f29-threshold-inferred-badge')).toBeInTheDocument(),
    );
  });

  it('renders data gaps section when gaps exist', async () => {
    mockEvaluationEndpoint();
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-data-gaps')).toBeInTheDocument());
    expect(screen.getByTestId('f29-data-gaps')).toHaveTextContent('13F_FEED_NOT_WIRED');
  });

  it('does NOT render data gaps section when no gaps', async () => {
    mockEvaluationEndpoint(makeF29Evaluation({ all_data_gaps: [] }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-entry-type-row')).toBeInTheDocument());
    expect(screen.queryByTestId('f29-data-gaps')).not.toBeInTheDocument();
  });

  it('greys out paths when regime precondition fails', async () => {
    mockEvaluationEndpoint(
      makeF29Evaluation({
        gate_status: 'BLOCKED',
        entry_type: 'BLOCKED_BY_REGIME',
        regime_precondition: {
          regime: 'CRISIS HALT',
          passed: false,
          reason: 'CRISIS HALT regime — no LEAPS regardless of entry type.',
          regime_undefined_flag: false,
        },
        discretionary_evaluation: null,
      }),
    );
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-paths')).toBeInTheDocument());
    expect(screen.getByTestId('f29-paths')).toHaveClass('is-f29-paths-greyed');
  });

  it('shows error state on API failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/framework29/evaluate/${TEST_TICKER}`, () =>
        HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 }),
      ),
    );
    renderCard();
    await waitFor(() => expect(screen.getByTestId('f29-error')).toBeInTheDocument());
  });
});
