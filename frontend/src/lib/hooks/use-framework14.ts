import { useQuery } from '@tanstack/react-query';

import { fetchFramework14 } from '@/lib/api/framework14';
import type { Framework14Result } from '@/lib/schemas/framework14';

/**
 * Fetch and cache the Framework 14 Position Sizing Rules evaluation for a ticker.
 *
 * Stale time is 0 — concentration status can change when the portfolio is updated.
 */
export function useFramework14(ticker: string): {
  data: Framework14Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework14', ticker],
    queryFn: () => fetchFramework14(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
