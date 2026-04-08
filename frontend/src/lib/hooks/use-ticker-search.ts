'use client';

import { useQuery } from '@tanstack/react-query';

import { searchTickers } from '@/lib/api/tickers';

/** Minimum query length before triggering a ticker search. */
const MIN_SEARCH_LENGTH = 1;

export function useTickerSearch(query: string) {
  return useQuery({
    queryKey: ['tickers', 'search', query],
    queryFn: () => searchTickers(query),
    enabled: query.length >= MIN_SEARCH_LENGTH,
    staleTime: 30_000, // 30 s — Polygon results don't change intraday
  });
}
