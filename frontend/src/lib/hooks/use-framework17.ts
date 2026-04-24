import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchFramework17Flag,
  fetchFramework17History,
  fetchFramework17Status,
  setFramework17Flag,
} from '@/lib/api/framework17';
import type {
  Framework17Result,
  Framework17SimpleResult,
  FlagHistoryEntry,
  SetFlagRequest,
} from '@/lib/schemas/framework17';

/**
 * 60-second stale time — matches backend F17 cache TTL.
 * Geo flag can change any time the operator acts.
 */
const STALE_MS = 60 * 1_000;

/** 5-minute stale time for flag history (changes infrequently). */
const HISTORY_STALE_MS = 5 * 60 * 1_000;

/** Query key factory for Framework 17. */
export const framework17Keys = {
  status: () => ['framework17', 'status'] as const,
  flag: () => ['framework17', 'flag'] as const,
  history: (days: number) => ['framework17', 'history', days] as const,
};

/**
 * Fetch and cache the full Framework 17 Geopolitical Monitor evaluation.
 *
 * Polls every 60 s — geo flag can change anytime.
 * Portfolio-level: does NOT re-fetch on ticker change.
 */
export function useFramework17(): {
  data: Framework17Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: framework17Keys.status(),
    queryFn: fetchFramework17Status,
    staleTime: STALE_MS,
    refetchInterval: STALE_MS,
  });
}

/**
 * Lightweight flag status for consuming frameworks.
 * Polls every 60 s.
 */
export function useFramework17Flag(): {
  data: Framework17SimpleResult | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  return useQuery({
    queryKey: framework17Keys.flag(),
    queryFn: fetchFramework17Flag,
    staleTime: STALE_MS,
    refetchInterval: STALE_MS,
  });
}

/**
 * Fetch flag history for the last N days.
 */
export function useFramework17History(days = 30): {
  data: FlagHistoryEntry[] | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  return useQuery({
    queryKey: framework17Keys.history(days),
    queryFn: () => fetchFramework17History(days),
    staleTime: HISTORY_STALE_MS,
  });
}

/**
 * Mutation: operator sets the geopolitical flag.
 * Invalidates F17, F27, and F28 queries on success.
 */
export function useSetFramework17Flag(): {
  mutate: (body: SetFlagRequest) => void;
  mutateAsync: (body: SetFlagRequest) => Promise<Framework17Result>;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
} {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: setFramework17Flag,
    onSuccess: () => {
      // Invalidate all F17 queries so next render shows fresh state.
      queryClient.invalidateQueries({ queryKey: ['framework17'] });
      // Also invalidate F27 and F28 since they depend on F17 state.
      queryClient.invalidateQueries({ queryKey: ['framework27'] });
      queryClient.invalidateQueries({ queryKey: ['framework28'] });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
  };
}
