import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchRegimeModifier } from '@/lib/api/regime-modifier';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';
import type { GeopoliticalState, RegimeModifierResponse } from '@/lib/schemas/regime-modifier';



/**
 * Fetch and cache the regime-adjusted conviction score for a given ticker.
 *
 * Reads the Framework 1 score from the existing `['framework-score', ticker]`
 * cache entry and passes it to the backend as `base_score` so F2 always uses
 * the same score value that F1 is currently displaying — eliminating any skew
 * between the two panels caused by independent fetch timings.
 *
 * The query is disabled when the ticker is empty. Changing the geopolitical
 * state is included in the query key so the effective regime stays in sync
 * with the morning briefing gate.
 */
export function useRegimeModifier(
  ticker: string,
  geopoliticalState: GeopoliticalState,
): {
  data: RegimeModifierResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ['regime-modifier', ticker, geopoliticalState],
    queryFn: () => {
      const cached = queryClient.getQueryData<FrameworkScoreResponse>([
        'framework-score',
        ticker,
      ]);
      return fetchRegimeModifier(ticker, geopoliticalState, cached?.final_score);
    },
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
