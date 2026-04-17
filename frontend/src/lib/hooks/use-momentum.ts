'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchMomentum } from '@/lib/api/momentum';

/** Query key factory for F1 momentum queries. */
export const momentumKey = (ticker: string) => ['momentum', 'f1', ticker] as const;

/** Minimum ticker length before triggering a momentum fetch. */
const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook that fetches the F1 Momentum score for the given ticker.
 * The query is disabled when ticker is an empty string.
 */
export function useMomentum(ticker: string) {
  return useQuery({
    queryKey: momentumKey(ticker),
    queryFn: () => fetchMomentum(ticker),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 0,
    retry: 1,
  });
}
