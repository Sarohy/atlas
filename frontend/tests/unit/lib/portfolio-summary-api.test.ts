import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import { adjustCash, fetchCash, fetchPortfolioSummary, updateCash } from '@/lib/api/portfolio-summary';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);
const mockApiPut = vi.mocked(client.apiPut);
const mockApiPost = vi.mocked(client.apiPost);

afterEach(() => vi.clearAllMocks());

const SUMMARY = {
  total_nav: 23900000,
  invested_value: 20315000,
  invested_pct: 85.0,
  cash_balance: 3585000,
  cash_pct: 15.0,
  cash_floor: 2390000,
  cash_floor_pct: 10.0,
  deployable: 1195000,
  day_change: -420000,
  beta_total: 1.09,
  beta_invested: 1.4,
};

const CASH = { cash_balance: 3585000, cash_floor_pct: 0.1 };

describe('fetchPortfolioSummary', () => {
  it('calls GET /api/v1/portfolio/summary and returns the summary', async () => {
    mockApiFetch.mockResolvedValueOnce(SUMMARY);
    const result = await fetchPortfolioSummary();
    expect(result).toEqual(SUMMARY);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/portfolio/summary', expect.anything());
  });
});

describe('fetchCash', () => {
  it('calls GET /api/v1/portfolio/cash and returns cash config', async () => {
    mockApiFetch.mockResolvedValueOnce(CASH);
    const result = await fetchCash();
    expect(result).toEqual(CASH);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/portfolio/cash', expect.anything());
  });
});

describe('updateCash', () => {
  it('calls PUT /api/v1/portfolio/cash with the payload and returns updated cash', async () => {
    mockApiPut.mockResolvedValueOnce({ cash_balance: 5000000, cash_floor_pct: 0.12 });
    const result = await updateCash({ cash_balance: 5000000, cash_floor_pct: 0.12 });
    expect(result).toEqual({ cash_balance: 5000000, cash_floor_pct: 0.12 });
    expect(mockApiPut).toHaveBeenCalledWith('/api/v1/portfolio/cash', expect.anything(), {
      cash_balance: 5000000,
      cash_floor_pct: 0.12,
    });
  });
});

describe('adjustCash', () => {
  it('calls POST /api/v1/portfolio/cash/adjust with the delta and returns updated cash', async () => {
    mockApiPost.mockResolvedValueOnce({ cash_balance: 3985000, cash_floor_pct: 0.1 });
    const result = await adjustCash(400000);
    expect(result).toEqual({ cash_balance: 3985000, cash_floor_pct: 0.1 });
    expect(mockApiPost).toHaveBeenCalledWith(
      '/api/v1/portfolio/cash/adjust',
      expect.anything(),
      { delta: 400000 },
    );
  });

  it('accepts a negative delta for cash withdrawal', async () => {
    mockApiPost.mockResolvedValueOnce({ cash_balance: 3555000, cash_floor_pct: 0.1 });
    await adjustCash(-30000);
    expect(mockApiPost).toHaveBeenCalledWith(
      '/api/v1/portfolio/cash/adjust',
      expect.anything(),
      { delta: -30000 },
    );
  });
});
