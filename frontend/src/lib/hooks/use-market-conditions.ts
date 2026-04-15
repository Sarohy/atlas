import { useQuery } from '@tanstack/react-query';

import { fetchMarketConditions } from '@/lib/api/market-conditions';
import type { MarketConditions } from '@/lib/schemas/market-conditions';

/**
 * Stale time: 5 minutes. Brent/VIX shift intraday but are the same for every
 * ticker, so one cached entry serves the entire session.
 */
/**
 * Fetch and cache the ticker-independent market conditions (Brent + VIX).
 *
 * A single cache entry is shared across all ticker views — switching tickers
 * does NOT trigger a new fetch.
 */
export function useMarketConditions(): {
  data: MarketConditions | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market-conditions'],
    queryFn: fetchMarketConditions,
    staleTime: 0,
    retry: 1,
  });
  return { data, isLoading, isError };
}
