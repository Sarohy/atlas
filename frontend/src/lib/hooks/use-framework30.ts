import { useQuery } from '@tanstack/react-query';

import { fetchFramework30Drawdown } from '@/lib/api/framework30';
import type { Framework30Result } from '@/lib/schemas/framework30';

/** 5-minute stale time — matches backend cache TTL (300 s). */
const STALE_MS = 5 * 60 * 1000;

/**
 * Fetch and cache the Framework 30 max drawdown gate evaluation.
 * Portfolio-level — no ticker parameter.
 */
export function useFramework30(): {
  data: Framework30Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework30'],
    queryFn: fetchFramework30Drawdown,
    staleTime: STALE_MS,
  });
}
