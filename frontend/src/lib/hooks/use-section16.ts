import { useQuery } from '@tanstack/react-query';

import { fetchSection16, fetchSection16ActiveCycles } from '@/lib/api/section16';
import type { ActiveCyclesSummary, Section16Result } from '@/lib/schemas/section16';

/** 60-second stale time — matches the F17/F12 cache pattern. */
const STALE_MS = 60 * 1000;

/**
 * Fetch and cache the full Section 16 exit rules evaluation for one ticker.
 */
export function useSection16(ticker: string): {
  data: Section16Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['section16', ticker],
    queryFn: () => fetchSection16(ticker),
    staleTime: STALE_MS,
    enabled: ticker.length > 0,
  });
}

/**
 * Fetch all tickers with active (non-CLEAR) exit rule cycles.
 */
export function useSection16ActiveCycles(): {
  data: ActiveCyclesSummary | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['section16', 'active-cycles'],
    queryFn: fetchSection16ActiveCycles,
    staleTime: STALE_MS,
  });
}
