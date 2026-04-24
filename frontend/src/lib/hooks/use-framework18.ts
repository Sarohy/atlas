import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchFramework18Status,
  refreshFramework18,
} from '@/lib/api/framework18';
import type { Framework18Result } from '@/lib/schemas/framework18';

// ── Query key factory ─────────────────────────────────────────────────────────
export const framework18Keys = {
  status: () => ['framework18', 'status'] as const,
} as const;

// Cache TTL matches the backend's 15-minute module-level cache (900 seconds).
// staleTime slightly less than backend TTL to re-fetch before cache expires.
const STALE_TIME_MS = 890_000; // 14 min 50 sec
const REFETCH_INTERVAL_MS = 900_000; // 15 min

/**
 * Portfolio-level Framework 18 status hook.
 * Does NOT re-fetch on ticker change — the SPY weekly trend is portfolio-wide.
 * Poll interval matches the backend's 15-minute cache TTL.
 */
export function useFramework18() {
  return useQuery<Framework18Result>({
    queryKey: framework18Keys.status(),
    queryFn: fetchFramework18Status,
    staleTime: STALE_TIME_MS,
    refetchInterval: REFETCH_INTERVAL_MS,
    retry: 2,
  });
}

/**
 * Mutation to force cache invalidation and re-fetch from Polygon.io.
 * Invalidates the local TanStack Query cache on success so the UI
 * immediately reflects the fresh result.
 */
export function useRefreshFramework18() {
  const queryClient = useQueryClient();

  return useMutation<Framework18Result, Error>({
    mutationFn: refreshFramework18,
    onSuccess: (data) => {
      queryClient.setQueryData(framework18Keys.status(), data);
    },
  });
}
