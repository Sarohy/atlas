import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { fetchAnalyst } from '@/lib/api/analyst';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);

afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// Shared fixtures — matches v7.3.4 F3 schema (base-score + modifier approach)
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
    base_score: 90,
  },
  analyst_coverage: {
    num_analysts: 38,
    modifier: 8,
  },
  pt_direction: {
    raises_30d: 3,
    lowers_30d: 0,
    direction_label: 'MULTIPLE_RAISES',
    modifier: 5,
  },
  recent_upgrades: {
    upgrades_30d: 5,
    downgrades_30d: 1,
    net_upgrades_30d: 4,
    modifier: 5,
  },
  pt_upside: {
    current_price: 182.5,
    consensus_pt: 230.0,
    upside_pct: 26.0,
    price_vs_target: -0.2065,
    price_vs_target_band: '20%+ below target (+10)',
    adjustment: 10,
  },
  f3_before_price_adjustment: 108,
  override_applied: false,
  override_reason: null,
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

  it('exposes pt_direction with raises_30d and lowers_30d', async () => {
    mockApiFetch.mockResolvedValueOnce(ANALYST_RESPONSE);

    const result = await fetchAnalyst('AAPL');

    expect(result.pt_direction.raises_30d).toBe(3);
    expect(result.pt_direction.lowers_30d).toBe(0);
    expect(result.pt_direction.direction_label).toBe('MULTIPLE_RAISES');
  });
});
