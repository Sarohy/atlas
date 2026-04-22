import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { fetchEarnings } from '@/lib/api/earnings';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);

afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const EARNINGS_RESPONSE = {
  ticker: 'AAPL',
  sf1_revenue_growth_pct: 65.0,
  sf1_score: 90,
  sf2_gross_margin_trend_bps: 120,
  sf2_score: 80,
  sf3_eps_beats: 4,
  sf3_quarters_available: 4,
  sf3_score: 100,
  sf3_excluded: false,
  sf4_guidance_delivered: null,
  sf4_score: 10,
  sf4_data_gap: true,
  sf5_forward_visibility_label: 'SPECIFIC_RAISED',
  sf5_score: 100,
  f2_raw: 87.5,
  f2_contribution: 21.875,
  f2_score: 88,
  f2_grade: 'STRONG BUY',
  pre_profit_status: false,
  pre_profit_reweighted: false,
  data_gap_applied: true,
  guidance_concern: false,
  exit_flag: false,
  limited_history: false,
  ipo_limited_history: false,
  data_available: true,
  is_pre_profitability: false,
  breakdown: {},
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('fetchEarnings', () => {
  it('calls apiFetch with the correct URL for a given ticker', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    await fetchEarnings('AAPL');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/earnings/AAPL', expect.anything());
  });

  it('upper-cases the ticker in the URL', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    await fetchEarnings('nvda');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/earnings/NVDA', expect.anything());
  });

  it('returns the parsed earnings response', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    const result = await fetchEarnings('AAPL');

    expect(result.ticker).toBe('AAPL');
    expect(result.f2_score).toBe(88);
    expect(result.f2_grade).toBe('STRONG BUY');
    expect(result.sf1_revenue_growth_pct).toBe(65.0);
    expect(result.sf4_data_gap).toBe(true);
  });
});
