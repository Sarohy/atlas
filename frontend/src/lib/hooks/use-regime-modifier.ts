import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchRegimeModifier } from '@/lib/api/regime-modifier';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';
import type { RegimeModifierResponse } from '@/lib/schemas/regime-modifier';



/**
 * Fetch and cache the regime-adjusted conviction score for a given ticker.
 *
 * Reads the Framework 1 score from the existing `['framework-score', ticker]`
 * cache entry and passes it to the backend as `base_score` so F2 always uses
 * the same score value that F1 is currently displaying — eliminating any skew
 * between the two panels caused by independent fetch timings.
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
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ['regime-modifier', ticker, activeWar],
    queryFn: () => {
      const cached = queryClient.getQueryData<FrameworkScoreResponse>([
        'framework-score',
        ticker,
      ]);
      return fetchRegimeModifier(ticker, activeWar, cached?.final_score);
    },
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
