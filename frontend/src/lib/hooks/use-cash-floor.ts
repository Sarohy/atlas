import { useQuery } from '@tanstack/react-query';

import { fetchCashFloor, fetchFramework5Status } from '@/lib/api/cash-floor';
import type { CashFloorResponse, Framework5Response } from '@/lib/schemas/cash-floor';

/**
 * Fetch and cache the Framework 5 portfolio-level cash floor status.
 *
 * No ticker required.  Stale time is 0 so each visit re-validates — Brent /
 * VIX can shift the regime at any point intraday.
 */
export function useFramework5(): {
  data: Framework5Response | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework5', 'status'],
    queryFn: fetchFramework5Status,
    staleTime: 0,
    retry: 1,
  });
}

/**
 * Fetch and cache the Framework 5 cash-floor guidance for a given ticker
 * (legacy — prefer useFramework5 for new code).
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
