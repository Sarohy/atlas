import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchPortfolioSummary, updateCash } from '@/lib/api/portfolio-summary';
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
