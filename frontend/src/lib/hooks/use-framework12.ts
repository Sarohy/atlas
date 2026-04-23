import { useQuery } from '@tanstack/react-query';

import {
  fetchFramework12,
  fetchFramework12PortfolioSummary,
} from '@/lib/api/framework12';
import type {
  Framework12PortfolioSummary,
  Framework12Result,
} from '@/lib/schemas/framework12';

/** 5-minute stale time — matches backend cache TTL (300 s). */
const STALE_MS = 5 * 60 * 1000;

/**
 * Fetch and cache the full Framework 12 no-fly evaluation for one ticker.
 */
export function useFramework12(ticker: string): {
  data: Framework12Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework12', ticker],
    queryFn: () => fetchFramework12(ticker),
    staleTime: STALE_MS,
    enabled: ticker.length > 0,
  });
}

/**
 * Fetch the portfolio-level Framework 12 summary.
 */
export function useFramework12PortfolioSummary(): {
  data: Framework12PortfolioSummary | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework12', 'portfolio', 'summary'],
    queryFn: fetchFramework12PortfolioSummary,
    staleTime: STALE_MS,
  });
}
