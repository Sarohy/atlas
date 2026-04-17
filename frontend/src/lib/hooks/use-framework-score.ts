import { useQuery } from '@tanstack/react-query';

import { fetchFrameworkScore } from '@/lib/api/framework-score';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';

/**
 * Fetch and cache the ATLAS Framework Score for a given ticker.
 *
 * staleTime: 0 — data is always considered stale so a background refetch is
 * triggered on every mount/focus. Cached data is still returned immediately
 * (no loading flicker) while the fresh fetch completes in the background.
 * This guarantees any ticker — new or existing — always reflects the latest
 * computed score regardless of when it was last fetched.
 */
export function useFrameworkScore(ticker: string): {
  data: FrameworkScoreResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework-score', ticker],
    queryFn: () => fetchFrameworkScore(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
