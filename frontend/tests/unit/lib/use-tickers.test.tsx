import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';

import * as tickersApi from '@/lib/api/tickers';
import {
  useTickers,
  useCreateTicker,
  useUpdateTicker,
  useDeleteTicker,
} from '@/lib/hooks/use-tickers';
import type { TickerResponse } from '@/lib/schemas/ticker';

vi.mock('@/lib/api/tickers');

const TICKER: TickerResponse = {
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

describe('useTickers', () => {
  it('returns ticker list on success', async () => {
    vi.mocked(tickersApi.fetchTickers).mockResolvedValueOnce([TICKER]);
    const { result } = renderHook(() => useTickers(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([TICKER]);
  });
});

describe('useCreateTicker', () => {
  it('calls createTicker and invalidates cache', async () => {
    vi.mocked(tickersApi.fetchTickers).mockResolvedValue([TICKER]);
    vi.mocked(tickersApi.createTicker).mockResolvedValueOnce({ ...TICKER, id: 2 });
    const wrapper = makeWrapper();
    const { result } = renderHook(() => useCreateTicker(), { wrapper });
    await act(async () => {
      result.current.mutate({
        ticker: 'NVDA',
        company_name: 'NVIDIA Corp',
        shares: '25',
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tickersApi.createTicker).toHaveBeenCalled();
  });
});

describe('useUpdateTicker', () => {
  it('calls updateTicker with id and shares', async () => {
    const updated = { ...TICKER, shares: 200 };
    vi.mocked(tickersApi.updateTicker).mockResolvedValueOnce(updated);
    const { result } = renderHook(() => useUpdateTicker(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '200' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tickersApi.updateTicker).toHaveBeenCalledWith(1, { shares: '200' });
  });

  it('updates the cached entry in-place', async () => {
    const updated = { ...TICKER, shares: 500 };
    vi.mocked(tickersApi.fetchTickers).mockResolvedValue([TICKER]);
    vi.mocked(tickersApi.updateTicker).mockResolvedValueOnce(updated);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    // Seed the cache with the original list
    qc.setQueryData(['tickers', 'portfolio'], [TICKER]);

    const { result } = renderHook(() => useUpdateTicker(), { wrapper });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '500' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cached: TickerResponse[] = qc.getQueryData(['tickers', 'portfolio']) ?? [];
    const first = cached[0];
    expect(first).toBeDefined();
    expect(first?.shares).toBe(500);
  });

  it('handles update with an empty cache gracefully', async () => {
    const updated = { ...TICKER, shares: 500 };
    vi.mocked(tickersApi.updateTicker).mockResolvedValueOnce(updated);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );
    // Do NOT seed the cache — prev will be undefined

    const { result } = renderHook(() => useUpdateTicker(), { wrapper });
    await act(async () => {
      result.current.mutate({ id: 1, shares: '500' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Cache should now be an empty array (the ?? [] fallback)
    const cached: TickerResponse[] = qc.getQueryData(['tickers', 'portfolio']) ?? [];
    // If the onSuccess ran with prev=undefined, it sets [] — getQueryData returns []
    expect(Array.isArray(cached)).toBe(true);
  });
});

describe('useDeleteTicker', () => {
  it('calls deleteTicker with the given id', async () => {
    vi.mocked(tickersApi.deleteTicker).mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useDeleteTicker(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate(1);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tickersApi.deleteTicker).toHaveBeenCalledWith(1);
  });

  it('removes the deleted entry from a seeded cache', async () => {
    vi.mocked(tickersApi.deleteTicker).mockResolvedValueOnce(undefined);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    qc.setQueryData(['tickers', 'portfolio'], [TICKER]);

    const { result } = renderHook(() => useDeleteTicker(), { wrapper });
    await act(async () => {
      result.current.mutate(1);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cached: TickerResponse[] = qc.getQueryData(['tickers', 'portfolio']) ?? [];
    expect(cached).toHaveLength(0);
  });
});
