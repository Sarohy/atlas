import { useQuery } from '@tanstack/react-query';

import { fetchFrameworkScore } from '@/lib/api/framework-score';
import type { FrameworkScoreResponse } from '@/lib/schemas/framework-score';

/** React Query stale time: 5 minutes (scores are intraday-stable). */
const STALE_TIME_MS = 5 * 60 * 1_000;

/**
 * Fetch and cache the ATLAS Framework Score for a given ticker.
 *
 * The query is disabled when the ticker is empty.  The result stays fresh
 * for 5 minutes before a background refetch is triggered.
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
    staleTime: STALE_TIME_MS,
    retry: 1,
  });
}
