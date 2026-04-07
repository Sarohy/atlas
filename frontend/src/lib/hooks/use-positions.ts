'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchPositions,
  createPosition,
  updatePosition,
  deletePosition,
  syncPositions,
} from '@/lib/api/positions';
import type { PositionResponse } from '@/lib/schemas/position';

/** Query key constant for the positions list. */
const POSITIONS_KEY = ['positions'] as const;

export function usePositions() {
  return useQuery({ queryKey: POSITIONS_KEY, queryFn: fetchPositions });
}

export function useCreatePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createPosition,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: POSITIONS_KEY });
    },
  });
}

export function useUpdatePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, shares }: { id: number; shares: string }) => updatePosition(id, { shares }),
    onSuccess: (updated: PositionResponse) => {
      qc.setQueryData<PositionResponse[]>(POSITIONS_KEY, (prev) =>
        (prev ?? []).map((p) => (p.id === updated.id ? updated : p)),
      );
    },
  });
}

export function useDeletePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deletePosition(id),
    onSuccess: (_: void, id: number) => {
      qc.setQueryData<PositionResponse[]>(POSITIONS_KEY, (prev) =>
        (prev ?? []).filter((p) => p.id !== id),
      );
    },
  });
}

export function useSyncPositions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: syncPositions,
    onSuccess: (updated: PositionResponse[]) => {
      qc.setQueryData<PositionResponse[]>(POSITIONS_KEY, updated);
    },
  });
}
