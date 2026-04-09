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
  revenue_growth: {
    current_ttm: 390000.0,
    prior_ttm: 330000.0,
    growth_pct: 18.2,
    score: 20,
    max_score: 20,
  },
  eps_beats: {
    beat_rate_pct: 100.0,
    quarters_beat: 4,
    score: 20,
    max_score: 20,
  },
  guidance: {
    revision_direction: 2,
    revision_pct: 12.5,
    score: 20,
    max_score: 20,
  },
  backlog_btb: {
    btb_proxy: 6.5,
    revenue_acceleration: 6.5,
    score: 20,
    max_score: 20,
  },
  margin_trajectory: {
    gross_margins: [42.0, 43.5, 44.2, 45.1],
    trajectory: 1.03,
    score: 20,
    max_score: 20,
  },
  f2_score: 100,
  f2_grade: 'STRONG BUY',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('fetchEarnings', () => {
  it('calls apiFetch with the correct URL for a given ticker', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    await fetchEarnings('AAPL');

    expect(mockApiFetch).toHaveBeenCalledWith(
      '/api/v1/earnings/AAPL',
      expect.anything(),
    );
  });

  it('upper-cases the ticker in the URL', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    await fetchEarnings('nvda');

    expect(mockApiFetch).toHaveBeenCalledWith(
      '/api/v1/earnings/NVDA',
      expect.anything(),
    );
  });

  it('returns the parsed earnings response', async () => {
    mockApiFetch.mockResolvedValueOnce(EARNINGS_RESPONSE);

    const result = await fetchEarnings('AAPL');

    expect(result.ticker).toBe('AAPL');
    expect(result.f2_score).toBe(100);
    expect(result.f2_grade).toBe('STRONG BUY');
    expect(result.revenue_growth.growth_pct).toBe(18.2);
  });
});
