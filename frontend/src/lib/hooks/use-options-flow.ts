'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchOptionsFlow } from '@/lib/api/options-flow';

/** Query key factory for F4 options flow queries. */
export const optionsFlowKey = (ticker: string) => ['options-flow', 'f4', ticker] as const;

/**
 * React Query hook that fetches the F4 Options Flow score for the given ticker.
 * The query is disabled when ticker is an empty string.
 *
 * Options flow data is real-time during market hours — stale after 5 minutes.
 */
export function useOptionsFlow(ticker: string) {
  return useQuery({
    queryKey: optionsFlowKey(ticker),
    queryFn: () => fetchOptionsFlow(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 5 * 60 * 1_000,
    retry: 1,
  });
}
