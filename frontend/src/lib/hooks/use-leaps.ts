import { useQuery } from '@tanstack/react-query';

import { fetchLeapsEligibility } from '@/lib/api/leaps';
import type { LeapsEligibility } from '@/lib/schemas/leaps';

/** 5-minute stale time — matches backend cache TTL (300 s). */
const STALE_MS = 5 * 60 * 1000;

/**
 * Fetch and cache the LEAPS eligibility result for a given ticker.
 * Re-fetches whenever ticker or score changes.
 *
 * Pass `score` to sync with the F1-panel adjusted score so Framework 10
 * displays the same value the investor already sees in Framework 1.
 */
export function useLeaps(
  ticker: string,
  score?: number,
): {
  data: LeapsEligibility | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['leaps', ticker, score],
    queryFn: () => fetchLeapsEligibility(ticker, score),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_MS,
  });
}
