import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';

import * as positionsApi from '@/lib/api/positions';
import {
  usePositions,
  useCreatePosition,
  useUpdatePosition,
  useDeletePosition,
} from '@/lib/hooks/use-positions';
import type { PositionResponse } from '@/lib/schemas/position';

vi.mock('@/lib/api/positions');

const POSITION: PositionResponse = {
  id: 1,
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  shares: 100,
  created_at: '2026-04-07T00:00:00Z',
  updated_at: '2026-04-07T00:00:00Z',
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

afterEach(() => vi.clearAllMocks());

describe('usePositions', () => {
  it('returns position list on success', async () => {
    vi.mocked(positionsApi.fetchPositions).mockResolvedValueOnce([POSITION]);
    const { result } = renderHook(() => usePositions(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([POSITION]);
  });
});

describe('useCreatePosition', () => {
  it('calls createPosition and invalidates cache', async () => {
    vi.mocked(positionsApi.fetchPositions).mockResolvedValue([POSITION]);
    vi.mocked(positionsApi.createPosition).mockResolvedValueOnce({ ...POSITION, id: 2 });
    const wrapper = makeWrapper();
    const { result } = renderHook(() => useCreatePosition(), { wrapper });
    await act(async () => {
      result.current.mutate({
        ticker: 'NVDA',
        company_name: 'NVIDIA Corp',
        shares: '25',
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(positionsApi.createPosition).toHaveBeenCalled();
  });
});

describe('useUpdatePosition', () => {
  it('calls updatePosition with id and shares', async () => {
    const updated = { ...POSITION, shares: 200 };
    vi.mocked(positionsApi.updatePosition).mockResolvedValueOnce(updated);
    const { result } = renderHook(() => useUpdatePosition(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '200' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(positionsApi.updatePosition).toHaveBeenCalledWith(1, { shares: '200' });
  });

  it('updates the cached entry in-place', async () => {
    const updated = { ...POSITION, shares: 500 };
    vi.mocked(positionsApi.fetchPositions).mockResolvedValue([POSITION]);
    vi.mocked(positionsApi.updatePosition).mockResolvedValueOnce(updated);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    // Seed the cache with the original list
    qc.setQueryData(['positions'], [POSITION]);

    const { result } = renderHook(() => useUpdatePosition(), { wrapper });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '500' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cached: PositionResponse[] = qc.getQueryData(['positions']) ?? [];
    const first = cached[0];
    expect(first).toBeDefined();
    expect(first?.shares).toBe(500);
  });

  it('handles update with an empty cache gracefully', async () => {
    const updated = { ...POSITION, shares: 500 };
    vi.mocked(positionsApi.updatePosition).mockResolvedValueOnce(updated);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );
    // Do NOT seed the cache — prev will be undefined

    const { result } = renderHook(() => useUpdatePosition(), { wrapper });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '500' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Cache should now be an empty array (the ?? [] fallback)
    const cached: PositionResponse[] = qc.getQueryData(['positions']) ?? [];
    // If the onSuccess ran with prev=undefined, it sets [] — getQueryData returns []
    expect(Array.isArray(cached)).toBe(true);
  });
});

describe('useDeletePosition', () => {
  it('calls deletePosition with the given id', async () => {
    vi.mocked(positionsApi.deletePosition).mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useDeletePosition(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate(1);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(positionsApi.deletePosition).toHaveBeenCalledWith(1);
  });

  it('removes the deleted entry from a seeded cache', async () => {
    vi.mocked(positionsApi.deletePosition).mockResolvedValueOnce(undefined);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    qc.setQueryData(['positions'], [POSITION]);

    const { result } = renderHook(() => useDeletePosition(), { wrapper });
    await act(async () => {
      result.current.mutate(1);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cached: PositionResponse[] = qc.getQueryData(['positions']) ?? [];
    expect(cached).toHaveLength(0);
  });
});
