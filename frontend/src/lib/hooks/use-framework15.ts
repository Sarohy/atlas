import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addOverride,
  fetchFramework15Status,
  fetchPausedOrders,
  fetchVixSnapshot,
  refreshFramework15,
  reviewPausedOrder,
} from '@/lib/api/framework15';
import type {
  AddOverrideRequest,
  Framework15Result,
  ReviewOrderRequest,
  VixSnapshot,
} from '@/lib/schemas/framework15';

/**
 * 60-second stale time — matches the backend cache TTL exactly.
 * F15 is intraday and VIX spikes can happen within a single minute.
 */
const STALE_MS = 60 * 1_000;

/** Query key factory for Framework 15. */
export const framework15Keys = {
  status: () => ['framework15', 'status'] as const,
  vixSnapshot: () => ['framework15', 'vix-snapshot'] as const,
  pausedOrders: () => ['framework15', 'paused-orders'] as const,
};

/**
 * Fetch and cache the full Framework 15 VIX Regime Override evaluation.
 *
 * Polls every 60 s while the market is open.
 * Polling stops automatically outside market hours.
 * This is a portfolio-level hook — does NOT re-fetch on ticker change.
 */
export function useFramework15(): {
  data: Framework15Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: framework15Keys.status(),
    queryFn: fetchFramework15Status,
    staleTime: STALE_MS,
    refetchInterval: (query) =>
      query.state.data?.market_open === true ? STALE_MS : false,
  });
}

/**
 * Fetch the VIX snapshot for Framework 25 — Liquidity Protocol.
 * Polls every 60 s during market hours.
 */
export function useVixSnapshot(): {
  data: VixSnapshot | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: framework15Keys.vixSnapshot(),
    queryFn: fetchVixSnapshot,
    staleTime: STALE_MS,
    refetchInterval: (query) =>
      query.state.data?.market_open === true ? STALE_MS : false,
  });
}

/**
 * Fetch today's paused orders.
 * Refreshes on demand or when the status changes.
 */
export function usePausedOrders() {
  return useQuery({
    queryKey: framework15Keys.pausedOrders(),
    queryFn: fetchPausedOrders,
    staleTime: STALE_MS,
  });
}

/**
 * Apply a human override for the current F15 session halt.
 * Invalidates the F15 status cache on success.
 */
export function useAddOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AddOverrideRequest) => addOverride(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: framework15Keys.status(),
      });
      void queryClient.invalidateQueries({
        queryKey: framework15Keys.pausedOrders(),
      });
    },
  });
}

/**
 * Record operator review decision for one paused order.
 * Invalidates the paused-orders cache on success.
 */
export function useReviewPausedOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      orderId,
      body,
    }: {
      orderId: number;
      body: ReviewOrderRequest;
    }) => reviewPausedOrder(orderId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: framework15Keys.pausedOrders(),
      });
    },
  });
}

/**
 * Force a cache refresh and re-evaluation of Framework 15.
 * Use this sparingly — the backend is already polling via refetchInterval.
 */
export function useRefreshFramework15() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshFramework15,
    onSuccess: (data) => {
      queryClient.setQueryData(framework15Keys.status(), data);
    },
  });
}
