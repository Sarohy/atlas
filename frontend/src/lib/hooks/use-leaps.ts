import { useQuery } from '@tanstack/react-query';

import { fetchLeapsEligibility } from '@/lib/api/leaps';
import type { LeapsEligibility } from '@/lib/schemas/leaps';

/** 5-minute stale time — matches backend cache TTL (300 s). */
const STALE_MS = 5 * 60 * 1000;

/**
 * Fetch and cache the LEAPS eligibility result for a given ticker.
 * Re-fetches whenever ticker changes.
 */
export function useLeaps(ticker: string): {
  data: LeapsEligibility | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['leaps', ticker],
    queryFn: () => fetchLeapsEligibility(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_MS,
  });
}
