import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { adjustCash, fetchPortfolioSummary, updateCash } from '@/lib/api/portfolio-summary';
import type { CashUpdate } from '@/lib/schemas/portfolio-summary';

/** React Query cache key for the portfolio summary. */
const PORTFOLIO_SUMMARY_KEY = ['portfolio', 'summary'] as const;

/** Fetch the computed portfolio summary (NAV, cash, beta, etc.). */
export function usePortfolioSummary() {
  return useQuery({
    queryKey: PORTFOLIO_SUMMARY_KEY,
    queryFn: fetchPortfolioSummary,
  });
}

/** Mutate the cash balance / floor; invalidates the summary on success. */
export function useUpdateCash() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CashUpdate) => updateCash(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PORTFOLIO_SUMMARY_KEY });
    },
  });
}

/**
 * Adjust the cash balance by a signed delta (positive = deposit, negative = withdrawal).
 * The backend clamps the result at zero. Invalidates the portfolio summary on success.
 */
export function useAdjustCash() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (delta: number) => adjustCash(delta),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PORTFOLIO_SUMMARY_KEY });
    },
  });
}
