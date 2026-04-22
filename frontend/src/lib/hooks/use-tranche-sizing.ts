import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { confirmTranche, fetchTrancheSizing } from '@/lib/api/tranche-sizing';
import type { TrancheSizingResponse } from '@/lib/schemas/tranche-sizing';

/** Stale time: 5 minutes — tranche values are driven by slow-moving signals. */
const STALE_TIME_MS = 5 * 60 * 1_000;

/**
 * Fetch and cache the Framework 4 tranche-sizing result.
 *
 * ``regimeRule`` should be passed from the parent's already-fetched Framework 2
 * value so this hook never triggers a second independent regime fetch — keeping
 * Framework 4 in sync with what Framework 2 is displaying.
 */
export function useTrancheSizing(
  ticker: string,
  initialCatalyst: 'yes' | 'no',
  regimeRule: string,
  iranResolution: string | null,
  brentConsecutiveBelow95Count: number = 0,
  geopoliticalState: string | null = null,
  brentPrice: number | null = null,
): {
  data: TrancheSizingResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: [
      'tranche-sizing',
      ticker,
      initialCatalyst,
      regimeRule,
      iranResolution,
      brentConsecutiveBelow95Count,
      geopoliticalState,
      brentPrice,
    ],
    queryFn: () =>
      fetchTrancheSizing(
        ticker,
        initialCatalyst,
        regimeRule,
        iranResolution,
        brentConsecutiveBelow95Count,
        geopoliticalState,
        brentPrice,
      ),
    enabled: ticker.trim().length >= 1,
    staleTime: STALE_TIME_MS,
    retry: 1,
  });
}

/**
 * Mutation hook to confirm an auto-triggered T2 or T3 tranche order.
 *
 * On success, invalidates the tranche-sizing query for the ticker so the
 * panel immediately reflects the fired state (t2_fired / t3_fired = true).
 */
export function useConfirmTranche(ticker: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tranche: 't2' | 't3') => confirmTranche(ticker, tranche),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tranche-sizing', ticker] });
    },
  });
}
