import { useQuery } from '@tanstack/react-query';

import { fetchFramework29Signals } from '@/lib/api/framework29';
import type { Framework29Result } from '@/lib/schemas/framework29';

/** 15-minute stale time — matches backend cache TTL (900 s). */
const STALE_MS = 15 * 60 * 1000;

/**
 * Fetch and cache the Framework 29 capitulation / re-entry evaluation.
 * Portfolio-level — no ticker parameter.
 */
export function useFramework29(): {
  data: Framework29Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework29'],
    queryFn: fetchFramework29Signals,
    staleTime: STALE_MS,
  });
}
