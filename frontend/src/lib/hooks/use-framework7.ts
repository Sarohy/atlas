import { useQuery } from '@tanstack/react-query';

import { fetchFramework7 } from '@/lib/api/framework7';
import type { EarningsGate } from '@/lib/schemas/framework7';

/**
 * Fetch and cache the Framework 7 Earnings Gate evaluation for a given ticker.
 *
 * `adjustedScore` is the score already displayed by the F1 panel
 * (= `final_score + regime_modifier`, clamped 0-100). Including it in the
 * query key re-runs the query whenever F1 or F2 data updates, and sends it
 * to the backend so the gate evaluates the same score the investor sees.
 *
 * Stale time is 0 — earnings dates and insider flags can change intraday.
 */
export function useFramework7(
  ticker: string,
  adjustedScore: number | undefined,
): {
  data: EarningsGate | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework7', ticker, adjustedScore],
    queryFn: () => fetchFramework7(ticker, adjustedScore),
    enabled: ticker.trim().length >= 1,
    staleTime: 0,
    retry: 1,
  });
}
