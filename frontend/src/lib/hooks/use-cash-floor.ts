import { useQuery } from '@tanstack/react-query';

import { fetchCashFloor } from '@/lib/api/cash-floor';
import type { CashFloorResponse } from '@/lib/schemas/cash-floor';

/**
 * Fetch and cache the Framework 5 cash-floor guidance for a given ticker.
 *
 * The query is disabled when the ticker is empty.  Stale time is 0 so each
 * visit re-validates — Brent / VIX can shift the condition at any point.
 */
export function useCashFloor(ticker: string): {
  data: CashFloorResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['cash-floor', ticker],
    queryFn: () => fetchCashFloor(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
