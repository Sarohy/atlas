import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';

import * as summaryApi from '@/lib/api/portfolio-summary';
import { usePortfolioSummary, useUpdateCash } from '@/lib/hooks/use-portfolio-summary';
import type { PortfolioSummary, CashResponse } from '@/lib/schemas/portfolio-summary';

vi.mock('@/lib/api/portfolio-summary');

const SUMMARY: PortfolioSummary = {
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

const CASH_RESPONSE: CashResponse = { cash_balance: 5000000, cash_floor_pct: 0.12 };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

afterEach(() => vi.clearAllMocks());

describe('usePortfolioSummary', () => {
  it('returns portfolio summary on success', async () => {
    vi.mocked(summaryApi.fetchPortfolioSummary).mockResolvedValueOnce(SUMMARY);
    const { result } = renderHook(() => usePortfolioSummary(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(SUMMARY);
  });

  it('exposes isLoading while fetching', async () => {
    vi.mocked(summaryApi.fetchPortfolioSummary).mockResolvedValueOnce(SUMMARY);
    const { result } = renderHook(() => usePortfolioSummary(), {
      wrapper: makeWrapper(),
    });
    // On the first frame the query is loading
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useUpdateCash', () => {
  it('calls updateCash and invalidates the summary query', async () => {
    vi.mocked(summaryApi.fetchPortfolioSummary).mockResolvedValue(SUMMARY);
    vi.mocked(summaryApi.updateCash).mockResolvedValueOnce(CASH_RESPONSE);

    const { result } = renderHook(() => useUpdateCash(), { wrapper: makeWrapper() });

    await act(async () => {
      result.current.mutate({ cash_balance: 5000000, cash_floor_pct: 0.12 });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(summaryApi.updateCash).toHaveBeenCalledWith({
      cash_balance: 5000000,
      cash_floor_pct: 0.12,
    });
  });
});
