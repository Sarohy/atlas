import { useQuery } from '@tanstack/react-query';

import { fetchF29Evaluation } from '@/lib/api/framework29';
import type { F29Evaluation } from '@/lib/schemas/framework29';

/** Sentinel used when no ticker has been selected yet. */
const EMPTY_TICKER = '';

/**
 * Fetch the Framework 29 three-path entry classifier for a ticker.
 * No caching — always fetches fresh data on every render cycle.
 * Hook is disabled when ticker is empty or whitespace.
 */
export function useF29Evaluation(ticker: string): {
  data: F29Evaluation | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  const enabled = ticker.trim().length > 0 && ticker !== EMPTY_TICKER;
  return useQuery({
    queryKey: ['f29Evaluation', ticker.toUpperCase()],
    queryFn: () => fetchF29Evaluation(ticker),
    staleTime: 0,
    gcTime: 0,
    enabled,
  });
}
