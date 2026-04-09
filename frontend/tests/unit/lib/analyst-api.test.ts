import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { fetchAnalyst } from '@/lib/api/analyst';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);

afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const ANALYST_RESPONSE = {
  ticker: 'AAPL',
  consensus_rating: {
    buy_count: 28,
    hold_count: 8,
    sell_count: 2,
    total_analysts: 38,
    buy_pct: 73.7,
    label: 'STRONG BUY',
    score: 20,
    max_score: 20,
  },
  pt_upside: {
    current_price: 182.5,
    consensus_pt: 230.0,
    upside_pct: 26.0,
    score: 20,
    max_score: 20,
  },
  pt_direction: {
    current_consensus_pt: 230.0,
    prior_consensus_pt: 210.0,
    direction_pct: 9.5,
    score: 20,
    max_score: 20,
  },
  analyst_coverage: {
    num_analysts: 38,
    score: 20,
    max_score: 20,
  },
  recent_upgrades: {
    upgrades: 5,
    downgrades: 1,
    net_upgrades: 4,
    score: 20,
    max_score: 20,
  },
  f3_score: 100,
  f3_grade: 'STRONG BUY',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('fetchAnalyst', () => {
  it('calls apiFetch with the correct URL for a given ticker', async () => {
    mockApiFetch.mockResolvedValueOnce(ANALYST_RESPONSE);

    await fetchAnalyst('AAPL');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/analyst/AAPL', expect.anything());
  });

  it('upper-cases the ticker in the URL', async () => {
    mockApiFetch.mockResolvedValueOnce(ANALYST_RESPONSE);

    await fetchAnalyst('nvda');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/analyst/NVDA', expect.anything());
  });

  it('returns the parsed analyst response', async () => {
    mockApiFetch.mockResolvedValueOnce(ANALYST_RESPONSE);

    const result = await fetchAnalyst('AAPL');

    expect(result.ticker).toBe('AAPL');
    expect(result.f3_score).toBe(100);
    expect(result.f3_grade).toBe('STRONG BUY');
    expect(result.consensus_rating.buy_pct).toBe(73.7);
  });
});
