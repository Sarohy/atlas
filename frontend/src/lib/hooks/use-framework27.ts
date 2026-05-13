import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchFramework27Contagion,
  postFramework27ManualFlag,
} from '@/lib/api/framework27';
import type {
  Framework27Result,
  ManualFlagRequest,
} from '@/lib/schemas/framework27';

// Cache TTL slightly under the backend's 5-minute module-level cache.
const STALE_TIME_MS = 290_000; // 4 min 50 sec
const REFETCH_INTERVAL_MS = 300_000; // 5 min

/** Query key factory for Framework 27. */
export const framework27Keys = {
  contagion: () => ['framework27', 'contagion'] as const,
} as const;

/**
 * Portfolio-level Framework 27 contagion map hook.
 * Polls every 5 minutes — matches the backend's module-level cache TTL.
 */
export function useFramework27(): {
  data: Framework27Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery<Framework27Result>({
    queryKey: framework27Keys.contagion(),
    queryFn: fetchFramework27Contagion,
    staleTime: STALE_TIME_MS,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

/**
 * Mutation to post an operator manual disruption flag.
 * Invalidates and replaces the contagion map cache on success.
 */
export function usePostFramework27ManualFlag() {
  const queryClient = useQueryClient();

  return useMutation<Framework27Result, Error, ManualFlagRequest>({
    mutationFn: postFramework27ManualFlag,
    onSuccess: (data) => {
      queryClient.setQueryData(framework27Keys.contagion(), data);
    },
  });
}
