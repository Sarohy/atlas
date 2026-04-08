'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createCluster, deleteCluster, fetchClusters, updateCluster } from '@/lib/api/clusters';
import type { ClusterCreate, ClusterResponse, ClusterUpdate } from '@/lib/schemas/cluster';

const CLUSTERS_KEY = ['clusters'] as const;

export function useClusters() {
  return useQuery({ queryKey: CLUSTERS_KEY, queryFn: fetchClusters });
}

export function useCreateCluster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClusterCreate) => createCluster(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CLUSTERS_KEY });
    },
  });
}

export function useUpdateCluster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ClusterUpdate }) => updateCluster(id, data),
    onSuccess: (updated: ClusterResponse) => {
      qc.setQueryData<ClusterResponse[]>(CLUSTERS_KEY, (prev) =>
        (prev ?? []).map((c) => (c.id === updated.id ? updated : c)),
      );
    },
  });
}

export function useDeleteCluster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteCluster(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CLUSTERS_KEY });
    },
  });
}
