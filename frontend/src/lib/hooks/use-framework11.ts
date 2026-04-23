import { useQuery } from '@tanstack/react-query';

import { fetchFramework11Status } from '@/lib/api/framework11';
import type { Framework11Result } from '@/lib/schemas/framework11';

/** 2-minute stale time — matches backend cache TTL (120 s). */
const STALE_MS = 2 * 60 * 1000;

/**
 * Fetch and cache the Framework 11 cash floor evaluation.
 * Portfolio-level — no ticker parameter.
 */
export function useFramework11(): {
  data: Framework11Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: ['framework11'],
    queryFn: fetchFramework11Status,
    staleTime: STALE_MS,
  });
}
