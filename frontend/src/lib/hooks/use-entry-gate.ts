import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query';

import { fetchEntryGate } from '@/lib/api/entry-gate';
import type { EntryGateResult } from '@/lib/schemas/entry-gate';

/** No client-side caching — backend re-fetches all market data on every call. */
const STALE_MS = 0;

const QUERY_KEY = (ticker: string): readonly unknown[] => ['entry-gate', ticker.toUpperCase()];

export function useEntryGate(ticker: string): {
  data: EntryGateResult | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: QUERY_KEY(ticker),
    queryFn: () => fetchEntryGate(ticker),
    enabled: ticker.length > 0,
    staleTime: STALE_MS,
    placeholderData: (prev) => prev,
  });
}

/** Invalidates the entry-gate query after mutations (track set, rule4, override). */
export function useInvalidateEntryGate(ticker: string): () => void {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: QUERY_KEY(ticker) });
  };
}
