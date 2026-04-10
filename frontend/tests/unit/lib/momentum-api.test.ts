import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { fetchMomentum } from '@/lib/api/momentum';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);

afterEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const MOMENTUM_RESPONSE = {
  ticker: 'AAPL',
  sector_etf: 'XLK',
  rsi: { value: 62.5, raw_score: 70, score: 14, max_score: 20 },
  macd: {
    macd_line: 1.23,
    signal_line: 0.98,
    histogram: 0.25,
    raw_score: 100,
    score: 15,
    max_score: 15,
  },
  ma_alignment: {
    ma_20: 175.0,
    ma_50: 170.0,
    ma_200: 160.0,
    label: 'ABOVE_ALL',
    raw_score: 100,
    score: 20,
    max_score: 20,
  },
  week_52_position: {
    high_52w: 200.0,
    low_52w: 140.0,
    position_pct: 75.0,
    raw_score: 80,
    score: 12,
    max_score: 15,
  },
  performance: {
    perf_1m: 7.5,
    perf_6m: 22.0,
    raw_score_1m: 85,
    raw_score_6m: 70,
    score_1m: 13,
    score_6m: 7,
    score: 20,
    max_score: 25,
  },
  sector_momentum: {
    sector_etf: 'XLK',
    ticker_perf_6m: 12.0,
    sector_perf_6m: 6.0,
    relative_perf_6m: 6.0,
    raw_score: 100,
    score: 5,
    max_score: 5,
  },
  f1_score: 86,
  f1_grade: 'STRONG BUY',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('fetchMomentum', () => {
  it('calls GET /api/v1/momentum/:ticker with the upper-cased symbol', async () => {
    mockApiFetch.mockResolvedValueOnce(MOMENTUM_RESPONSE);

    await fetchMomentum('aapl');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/momentum/AAPL', expect.anything());
  });

  it('returns the parsed momentum response', async () => {
    mockApiFetch.mockResolvedValueOnce(MOMENTUM_RESPONSE);

    const result = await fetchMomentum('AAPL');

    expect(result.ticker).toBe('AAPL');
    expect(result.f1_score).toBe(86);
    expect(result.f1_grade).toBe('STRONG BUY');
    expect(result.rsi.value).toBe(62.5);
    expect(result.macd.histogram).toBe(0.25);
    expect(result.ma_alignment.label).toBe('ABOVE_ALL');
    expect(result.week_52_position.position_pct).toBe(75.0);
    expect(result.performance.score_1m).toBe(13);
    expect(result.sector_momentum.relative_perf_6m).toBe(6.0);
  });

  it('encodes special characters in the ticker symbol', async () => {
    mockApiFetch.mockResolvedValueOnce({ ...MOMENTUM_RESPONSE, ticker: 'BRK.B' });

    await fetchMomentum('brk.b');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/momentum/BRK.B', expect.anything());
  });
});
