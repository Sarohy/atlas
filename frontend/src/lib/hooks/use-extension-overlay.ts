'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchExtensionOverlay } from '@/lib/api/extension-overlay';

/** Query key factory for extension-overlay queries (keyed by ticker + score). */
export const extensionOverlayKey = (ticker: string, atlasScore?: number | null) =>
  ['extension-overlay', ticker, atlasScore ?? null] as const;

const MIN_TICKER_LENGTH = 1;

/**
 * React Query hook for the Overbought / Extension Overlay.
 * Disabled until a ticker is selected. The atlas score (when provided) drives
 * the action matrix and is part of the cache key so the action refreshes when
 * the conviction score changes.
 */
export function useExtensionOverlay(ticker: string, atlasScore?: number | null) {
  return useQuery({
    queryKey: extensionOverlayKey(ticker, atlasScore),
    queryFn: () => fetchExtensionOverlay(ticker, atlasScore),
    enabled: ticker.trim().length >= MIN_TICKER_LENGTH,
    staleTime: 0,
    retry: 1,
  });
}
