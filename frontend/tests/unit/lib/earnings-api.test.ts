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
    yoy_pct: 65.0,
    raw_score: 90,
    score: 27,
    max_score: 30,
  },
  eps_beats: {
    beats_in_3: 3,
    quarters_checked: 3,
    raw_score: 100,
    score: 20,
    max_score: 20,
  },
  guidance: {
    guidance_label: 'NO_DATA_AVAILABLE',
    transcript_quarter: null,
    raw_score: 50,
    score: 10,
    max_score: 20,
  },
  margin_trajectory: {
    gross_margins: [43.0, 44.0, 45.0],
    margin_change_pts: 2.0,
    raw_score: 80,
    score: 12,
    max_score: 15,
  },
  backlog_btb: {
    backlog_label: 'EXPLICIT_MULTI_QUARTER',
    raw_score: 100,
    score: 15,
    max_score: 15,
  },
  f2_score: 84,
  f2_grade: 'STRONG BUY',
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
    expect(result.f2_score).toBe(84);
    expect(result.f2_grade).toBe('STRONG BUY');
    expect(result.revenue_growth.yoy_pct).toBe(65.0);
  });
});
