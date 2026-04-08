'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  syncWatchlist,
} from '@/lib/api/watchlist';
import type { WatchlistItemResponse } from '@/lib/schemas/watchlist';

const WATCHLIST_KEY = ['watchlist'] as const;

export function useWatchlist() {
  return useQuery({ queryKey: WATCHLIST_KEY, queryFn: fetchWatchlist });
}

export function useAddToWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: WATCHLIST_KEY });
    },
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => removeFromWatchlist(id),
    onSuccess: (_: void, id: number) => {
      qc.setQueryData<WatchlistItemResponse[]>(WATCHLIST_KEY, (prev) =>
        (prev ?? []).filter((item) => item.id !== id),
      );
    },
  });
}

export function useSyncWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: syncWatchlist,
    onSuccess: (updated: WatchlistItemResponse[]) => {
      qc.setQueryData<WatchlistItemResponse[]>(WATCHLIST_KEY, updated);
    },
  });
}
