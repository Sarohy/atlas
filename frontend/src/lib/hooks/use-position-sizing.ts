import { useQuery } from '@tanstack/react-query';

import { fetchPositionSizing } from '@/lib/api/position-sizing';
import type { PositionSizingResponse } from '@/lib/schemas/position-sizing';

const STALE_TIME_MS = 5 * 60 * 1_000;

export function usePositionSizing(
  ticker: string,
  baseScore?: number,
): {
  data: PositionSizingResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['position-sizing', ticker, baseScore],
    queryFn: () => fetchPositionSizing(ticker, baseScore),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_TIME_MS,
    retry: 1,
  });
}
