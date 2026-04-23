import { useQuery } from '@tanstack/react-query';

import { fetchFramework9 } from '@/lib/api/framework9';
import type { Framework9Result } from '@/lib/schemas/framework9';

/**
 * Fetch and cache the Framework 9 options flow evaluation for a given ticker.
 *
 * Results are stale after 15 minutes (matching the backend in-memory cache TTL).
 */
export function useFramework9(ticker: string): {
  data: Framework9Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  // 15-minute stale time — matches backend cache TTL (900 s).
  const STALE_MS = 15 * 60 * 1000;

  return useQuery({
    queryKey: ['framework9', ticker],
    queryFn: () => fetchFramework9(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_MS,
  });
}
