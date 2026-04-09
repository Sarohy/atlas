import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { fetchAnalyst } from '@/lib/api/analyst';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);

afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// Shared fixtures — matches new 4-indicator F3 schema (Factor_Mapping_Guide)
// ---------------------------------------------------------------------------

const ANALYST_RESPONSE = {
  ticker: 'AAPL',
  consensus_rating: {
    strong_buy_count: 10,
    buy_count: 18,
    hold_count: 8,
    sell_count: 2,
    strong_sell_count: 0,
    total_analysts: 38,
    buy_pct: 73.7,
    label: 'STRONG BUY',
    score: 100,
    weight: 0.35,
  },
  analyst_coverage: {
    num_analysts: 38,
    score: 100,
    weight: 0.10,
  },
  pt_upside: {
    current_price: 182.5,
    consensus_pt: 230.0,
    upside_pct: 26.0,
    score: 85,
    weight: 0.30,
  },
  pt_revision: {
    raises_30d: 3,
    lowers_30d: 0,
    revision_label: 'MULTIPLE RAISES',
    score: 100,
    weight: 0.25,
  },
  // F3 = (100×0.35) + (100×0.10) + (85×0.30) + (100×0.25) = 35 + 10 + 25.5 + 25 = 95.5 → 96
  f3_score: 96,
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
    expect(result.f3_score).toBe(96);
    expect(result.f3_grade).toBe('STRONG BUY');
    expect(result.consensus_rating.buy_pct).toBe(73.7);
  });

  it('exposes pt_revision with raises_30d and lowers_30d', async () => {
    mockApiFetch.mockResolvedValueOnce(ANALYST_RESPONSE);

    const result = await fetchAnalyst('AAPL');

    expect(result.pt_revision.raises_30d).toBe(3);
    expect(result.pt_revision.lowers_30d).toBe(0);
    expect(result.pt_revision.revision_label).toBe('MULTIPLE RAISES');
  });
});
