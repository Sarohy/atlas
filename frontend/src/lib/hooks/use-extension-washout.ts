'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchExtensionWashout } from '@/lib/api/extension-washout';

/** Query key for extension-washout queries (keyed by ticker + weight + catalyst). */
export const extensionWashoutKey = (
  ticker: string,
  positionWeightPct?: number | null,
  negativeCatalyst = false,
  beta?: number | null,
) =>
  ['extension-washout', ticker, positionWeightPct ?? null, negativeCatalyst, beta ?? null] as const;

const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook for the Extension & Washout Overlay (Spec v2 + v2.1). Disabled
 * until a ticker is selected. Position weight drives the §3.1 gate; beta feeds
 * the overshoot-elasticity score.
 */
export function useExtensionWashout(
  ticker: string,
  positionWeightPct?: number | null,
  negativeCatalyst = false,
  beta?: number | null,
) {
  return useQuery({
    queryKey: extensionWashoutKey(ticker, positionWeightPct, negativeCatalyst, beta),
    queryFn: () => fetchExtensionWashout(ticker, positionWeightPct, negativeCatalyst, beta),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 0,
    retry: 1,
  });
}
