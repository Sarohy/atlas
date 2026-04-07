import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/lib/api/client';
import {
  fetchPositions,
  createPosition,
  updatePosition,
  deletePosition,
  searchTickers,
} from '@/lib/api/positions';

vi.mock('@/lib/api/client');

const mockApiFetch = vi.mocked(client.apiFetch);
const mockApiPost = vi.mocked(client.apiPost);
const mockApiPatch = vi.mocked(client.apiPatch);
const mockApiDelete = vi.mocked(client.apiDelete);

afterEach(() => vi.clearAllMocks());

const POSITION = {
  id: 1,
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  shares: '100',
  created_at: '2026-04-07T00:00:00Z',
  updated_at: '2026-04-07T00:00:00Z',
};

describe('fetchPositions', () => {
  it('calls GET /api/v1/positions and returns a list', async () => {
    mockApiFetch.mockResolvedValueOnce([POSITION]);
    const result = await fetchPositions();
    expect(result).toEqual([POSITION]);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/positions', expect.anything());
  });
});

describe('createPosition', () => {
  it('calls POST /api/v1/positions with the payload', async () => {
    mockApiPost.mockResolvedValueOnce({ ...POSITION, id: 2 });
    await createPosition({ ticker: 'NVDA', company_name: 'NVIDIA Corp', shares: '25' });
    expect(mockApiPost).toHaveBeenCalledWith(
      '/api/v1/positions',
      expect.anything(),
      expect.objectContaining({ ticker: 'NVDA' }),
    );
  });
});

describe('updatePosition', () => {
  it('calls PATCH /api/v1/positions/:id with updated shares', async () => {
    mockApiPatch.mockResolvedValueOnce({ ...POSITION, shares: '200' });
    await updatePosition(1, { shares: '200' });
    expect(mockApiPatch).toHaveBeenCalledWith(
      '/api/v1/positions/1',
      expect.anything(),
      expect.objectContaining({ shares: '200' }),
    );
  });
});

describe('deletePosition', () => {
  it('calls DELETE /api/v1/positions/:id', async () => {
    mockApiDelete.mockResolvedValueOnce(undefined);
    await deletePosition(1);
    expect(mockApiDelete).toHaveBeenCalledWith('/api/v1/positions/1');
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
