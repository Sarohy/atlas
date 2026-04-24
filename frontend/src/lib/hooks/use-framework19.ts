import { useQuery } from '@tanstack/react-query';
import { fetchFramework19Status } from '@/lib/api/framework19';
import type { Framework19Result } from '@/lib/schemas/framework19';

// ── Query key factory ─────────────────────────────────────────────────────────

export const framework19Keys = {
  status: () => ['framework19', 'status'] as const,
} as const;

/**
 * 2-minute polling interval for NVDA kill-switch monitoring.
 * Matches the APScheduler 2-minute poll on the backend.
 *
 * ZERO caching intent: staleTime is 0 so every refetch delivers fresh data.
 * The backend makes a live Polygon.io call on every request.
 */
const REFETCH_INTERVAL_MS = 120_000; // 2 minutes — matches APScheduler interval

/**
 * Portfolio-level Framework 19 status hook.
 *
 * Does NOT re-fetch on ticker change — the NVDA kill switch is portfolio-wide.
 * Polls every 2 minutes when market is open; pauses polling outside hours.
 *
 * Zero staleTime — every background refetch is treated as fresh data needed.
 */
export function useFramework19() {
  const query = useQuery<Framework19Result>({
    queryKey: framework19Keys.status(),
    queryFn: fetchFramework19Status,
    // Zero staleTime: F19 is never cached — always fetch fresh.
    staleTime: 0,
    refetchInterval: (query) => {
      // Stop polling when market is closed to avoid unnecessary Polygon calls.
      const data = query.state.data;
      if (data && !data.market_open) {
        return false;
      }
      return REFETCH_INTERVAL_MS;
    },
    retry: 1,
  });

  return query;
}
