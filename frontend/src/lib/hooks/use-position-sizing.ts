import { useQuery } from '@tanstack/react-query';

import { fetchPositionSizing } from '@/lib/api/position-sizing';
import type { PositionSizingResponse } from '@/lib/schemas/position-sizing';

const STALE_TIME_MS = 5 * 60 * 1_000;

export function usePositionSizing(
  ticker: string,
  baseScore?: number,
  concentrationCapActive?: boolean,
  /** Set to false to suspend the query (e.g. while waiting for F1 score). */
  enabled = true,
): {
  data: PositionSizingResponse | undefined;
  /** True while waiting for F1 or while actively fetching. */
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  const result = useQuery({
    queryKey: ['position-sizing', ticker, baseScore, concentrationCapActive],
    queryFn: () => fetchPositionSizing(ticker, baseScore, concentrationCapActive),
    enabled: enabled && ticker.trim().length >= 1,
    staleTime: STALE_TIME_MS,
    retry: 1,
  });

  return {
    data: result.data,
    // Treat "waiting for prerequisite" the same as loading so the panel
    // shows the loading state rather than "no data" while F1 is in-flight.
    isLoading: result.isPending || result.isFetching,
    isError: result.isError,
    error: result.error,
  };
}
