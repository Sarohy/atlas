import { useQuery } from '@tanstack/react-query';

import { fetchFramework12 } from '@/lib/api/framework12';
import type { Framework12Result } from '@/lib/schemas/framework12';

/** No client-side caching — backend re-fetches all market data on every call. */
const STALE_MS = 0;

export function useFramework12(ticker: string): {
  data: Framework12Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework12', ticker.toUpperCase()],
    queryFn: () => fetchFramework12(ticker),
    enabled: ticker.length > 0,
    staleTime: STALE_MS,
  });
}
