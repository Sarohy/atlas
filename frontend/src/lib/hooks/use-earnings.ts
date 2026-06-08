'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchEarnings } from '@/lib/api/earnings';

/** Query key factory for F2 earnings queries. */
export const earningsKey = (ticker: string) => ['earnings', 'f2', ticker] as const;

/** Minimum ticker length before triggering an earnings fetch. */
const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook that fetches the F2 Earnings Quality score for the given ticker.
 * The query is disabled when ticker is an empty string.
 */
export function useEarnings(ticker: string) {
  return useQuery({
    queryKey: earningsKey(ticker),
    queryFn: () => fetchEarnings(ticker),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
