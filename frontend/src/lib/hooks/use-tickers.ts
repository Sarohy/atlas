'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchTickers,
  createTicker,
  updateTicker,
  deleteTicker,
  syncTickers,
} from '@/lib/api/tickers';
import type { TickerResponse } from '@/lib/schemas/ticker';

/** Query key constant for the tickers list. */
const TICKERS_KEY = ['tickers', 'portfolio'] as const;

export function useTickers() {
  return useQuery({ queryKey: TICKERS_KEY, queryFn: fetchTickers });
}

export function useCreateTicker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTicker,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: TICKERS_KEY });
    },
  });
}

export function useUpdateTicker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      shares,
      cluster_id,
    }: {
      id: number;
      shares: string;
      cluster_id?: number | null;
    }) => updateTicker(id, { shares, cluster_id }),
    onSuccess: (updated: TickerResponse) => {
      qc.setQueryData<TickerResponse[]>(TICKERS_KEY, (prev) =>
        (prev ?? []).map((t) => (t.id === updated.id ? updated : t)),
      );
    },
  });
}

export function useDeleteTicker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteTicker(id),
    onSuccess: (_: void, id: number) => {
      qc.setQueryData<TickerResponse[]>(TICKERS_KEY, (prev) =>
        (prev ?? []).filter((t) => t.id !== id),
      );
    },
  });
}

export function useSyncTickers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: syncTickers,
    onSuccess: (updated: TickerResponse[]) => {
      qc.setQueryData<TickerResponse[]>(TICKERS_KEY, updated);
    },
  });
}
