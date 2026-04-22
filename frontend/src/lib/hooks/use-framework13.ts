import { useQuery } from '@tanstack/react-query';

import { fetchFramework13 } from '@/lib/api/framework13';
import type { Framework13Result } from '@/lib/schemas/framework13';

/**
 * Fetch and cache the Framework 13 beta cap evaluation for a ticker.
 *
 * Stale time is 0 — beta cap status must reflect the latest portfolio weight.
 */
export function useFramework13(ticker: string): {
  data: Framework13Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework13', ticker],
    queryFn: () => fetchFramework13(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
