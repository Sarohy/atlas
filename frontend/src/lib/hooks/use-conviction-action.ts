import { useQuery } from '@tanstack/react-query';

import { fetchConvictionAction } from '@/lib/api/conviction-action';
import type { ConvictionActionResponse } from '@/lib/schemas/conviction-action';

/**
 * Fetch and cache the Framework 6 conviction-action guidance for a given ticker.
 *
 * `adjustedScore` is the score already displayed by the F1 panel
 * (= `final_score + regime_modifier`, clamped 0–100). Including it in the
 * query key re-runs the query whenever F1 or F2 data updates. The backend
 * uses this value directly, skipping the regime service, so the modifier is
 * applied exactly once (by F2 / F1’s own calculation).
 */
export function useConvictionAction(
  ticker: string,
  adjustedScore: number | undefined,
): {
  data: ConvictionActionResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['conviction-action', ticker, adjustedScore],
    queryFn: () => fetchConvictionAction(ticker, adjustedScore),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
