'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchFundamental } from '@/lib/api/fundamental';

/** Query key factory for F5 fundamental queries. */
export const fundamentalKey = (ticker: string) => ['fundamental', 'f5', ticker] as const;

/**
 * React Query hook that fetches the F5 Fundamental Quality score for the given ticker.
 * The query is disabled when ticker is an empty string.
 *
 * Fundamental data updates quarterly after earnings — stale after 24 hours.
 */
export function useFundamental(ticker: string) {
  return useQuery({
    queryKey: fundamentalKey(ticker),
    queryFn: () => fetchFundamental(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 24 * 60 * 60 * 1_000,
    retry: 1,
  });
}
