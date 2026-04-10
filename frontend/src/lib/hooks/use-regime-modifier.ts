import { useQuery } from '@tanstack/react-query';

import { fetchRegimeModifier } from '@/lib/api/regime-modifier';
import type { RegimeModifierResponse } from '@/lib/schemas/regime-modifier';

/** React Query stale time: 2 minutes (market regime can shift intraday). */
const STALE_TIME_MS = 2 * 60 * 1_000;

/**
 * Fetch and cache the regime-adjusted conviction score for a given ticker.
 *
 * The query is disabled when the ticker is empty. Changing `activeWar` is
 * included in the query key so toggling the war flag triggers a fresh fetch.
 */
export function useRegimeModifier(
  ticker: string,
  activeWar: boolean,
): {
  data: RegimeModifierResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['regime-modifier', ticker, activeWar],
    queryFn: () => fetchRegimeModifier(ticker, activeWar),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_TIME_MS,
    retry: 1,
  });
}
