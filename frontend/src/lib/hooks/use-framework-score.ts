import { useQuery } from '@tanstack/react-query';

import { fetchFrameworkScore } from '@/lib/api/framework-score';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';

/**
 * Fetch and cache the ATLAS Framework Score for a given ticker.
 *
 * Use a short stale window to reduce duplicate third-party fetch bursts while
 * keeping the panel responsive to new data.
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
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
