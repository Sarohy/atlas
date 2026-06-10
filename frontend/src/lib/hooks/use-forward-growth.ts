'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchForwardGrowth } from '@/lib/api/forward-growth';

type Scores = {
  f5?: number | null;
  f4?: number | null;
  atlas?: number | null;
};

/** Query key — keyed by ticker + the scores so the bucket refreshes when they change. */
export const forwardGrowthKey = (ticker: string, scores: Scores) =>
  ['forward-growth', ticker, scores.f5 ?? null, scores.f4 ?? null, scores.atlas ?? null] as const;

const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook for the Forward Growth Score. The F5/F4/ATLAS scores drive the
 * action-matrix bucket and are part of the cache key.
 */
export function useForwardGrowth(ticker: string, scores: Scores = {}) {
  return useQuery({
    queryKey: forwardGrowthKey(ticker, scores),
    queryFn: () => fetchForwardGrowth(ticker, scores),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 0,
    retry: 1,
  });
}
