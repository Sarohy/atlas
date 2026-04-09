'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchAnalyst } from '@/lib/api/analyst';

/** Query key factory for F3 analyst queries. */
export const analystKey = (ticker: string) => ['analyst', 'f3', ticker] as const;

/** Minimum ticker length before triggering an analyst fetch. */
const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook that fetches the F3 Analyst Conviction score for the given ticker.
 * The query is disabled when ticker is an empty string.
 *
 * Analyst consensus data changes slowly — stale after 60 minutes.
 */
export function useAnalyst(ticker: string) {
  return useQuery({
    queryKey: analystKey(ticker),
    queryFn: () => fetchAnalyst(ticker),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    // Analyst consensus changes slowly — stale after 60 minutes.
    staleTime: 60 * 60 * 1_000,
    retry: 1,
  });
}
