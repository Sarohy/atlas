'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchOptionsFlow } from '@/lib/api/options-flow';

/** Query key factory for F4 options flow queries. */
export const optionsFlowKey = (ticker: string) => ['options-flow', 'f4', ticker] as const;

/**
 * React Query hook that fetches the F4 Options Flow score for the given ticker.
 * The query is disabled when ticker is an empty string.
 *
 * F4 v2 reads a 5-session rolling window directly from the providers on every
 * call — caching is disabled (per spec Q6) so the panel always reflects the
 * latest dark-pool + options prints.
 */
export function useOptionsFlow(ticker: string) {
  return useQuery({
    queryKey: optionsFlowKey(ticker),
    queryFn: () => fetchOptionsFlow(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    gcTime: 0,
    retry: 1,
  });
}
