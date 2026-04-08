import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import {
  fetchTickers,
  createTicker,
  updateTicker,
  deleteTicker,
  searchTickers,
} from '@/lib/api/tickers';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);
const mockApiPost = vi.mocked(client.apiPost);
const mockApiPatch = vi.mocked(client.apiPatch);
const mockApiDelete = vi.mocked(client.apiDelete);

afterEach(() => vi.clearAllMocks());

const TICKER = {
  id: 1,
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  shares: '100',
  created_at: '2026-04-07T00:00:00Z',
  updated_at: '2026-04-07T00:00:00Z',
};

describe('fetchTickers', () => {
  it('calls GET /api/v1/tickers and returns a list', async () => {
    mockApiFetch.mockResolvedValueOnce([TICKER]);
    const result = await fetchTickers();
    expect(result).toEqual([TICKER]);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/tickers', expect.anything());
  });
});

describe('createTicker', () => {
  it('calls POST /api/v1/tickers with the payload', async () => {
    mockApiPost.mockResolvedValueOnce({ ...TICKER, id: 2 });
    await createTicker({ ticker: 'NVDA', company_name: 'NVIDIA Corp', shares: '25' });
    expect(mockApiPost).toHaveBeenCalledWith(
      '/api/v1/tickers',
      expect.anything(),
      expect.objectContaining({ ticker: 'NVDA' }),
    );
  });
});

describe('updateTicker', () => {
  it('calls PATCH /api/v1/tickers/:id with updated shares', async () => {
    mockApiPatch.mockResolvedValueOnce({ ...TICKER, shares: '200' });
    await updateTicker(1, { shares: '200' });
    expect(mockApiPatch).toHaveBeenCalledWith(
      '/api/v1/tickers/1',
      expect.anything(),
      expect.objectContaining({ shares: '200' }),
    );
  });
});

describe('deleteTicker', () => {
  it('calls DELETE /api/v1/tickers/:id', async () => {
    mockApiDelete.mockResolvedValueOnce(undefined);
    await deleteTicker(1);
    expect(mockApiDelete).toHaveBeenCalledWith('/api/v1/tickers/1');
  });
});

describe('searchTickers', () => {
  it('calls GET /api/v1/tickers/search with the query param', async () => {
    mockApiFetch.mockResolvedValueOnce([
      { ticker: 'AAPL', name: 'Apple Inc.', market: 'stocks', type: 'CS' },
    ]);
    const results = await searchTickers('apple');
    expect(results).toHaveLength(1);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/tickers/search?q=apple', expect.anything());
  });
});
