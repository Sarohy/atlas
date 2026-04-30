import { useQuery } from '@tanstack/react-query';

import { fetchFramework8 } from '@/lib/api/framework8';
import type { Framework8Response } from '@/lib/schemas/framework8';

/**
 * Fetch and cache the Framework 8 insider activity analysis for a given ticker.
 *
 * Results are cached for 24 hours (matching the backend cache TTL) because
 * SEC EDGAR Form 4 filings are not intraday events.
 */
export function useFramework8(ticker: string): {
  data: Framework8Response | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  // 24-hour stale time — Form 4 filings are not intraday events.
  const STALE_MS = 24 * 60 * 60 * 1000;

  return useQuery({
    queryKey: ['framework8', ticker],
    queryFn: () => fetchFramework8(ticker),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_MS,
    retry: 1,
  });
}
