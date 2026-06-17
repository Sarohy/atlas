'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchExtensionOverlay } from '@/lib/api/extension-overlay';

/** Query key factory for extension-overlay queries (keyed by ticker + scores). */
export const extensionOverlayKey = (
  ticker: string,
  atlasScore?: number | null,
  f4Score?: number | null,
) => ['extension-overlay', ticker, atlasScore ?? null, f4Score ?? null] as const;

const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook for the Overbought / Extension Overlay.
 * Disabled until a ticker is selected. The atlas score drives the action matrix;
 * the F4 options-flow score gates a full ADD vs STARTER / WATCH. Both are part of
 * the cache key so the action refreshes when either score changes.
 */
export function useExtensionOverlay(
  ticker: string,
  atlasScore?: number | null,
  f4Score?: number | null,
) {
  return useQuery({
    queryKey: extensionOverlayKey(ticker, atlasScore, f4Score),
    queryFn: () => fetchExtensionOverlay(ticker, atlasScore, f4Score),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 0,
    retry: 1,
  });
}
