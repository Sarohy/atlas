import { z } from 'zod';

import { apiFetch, apiPost, apiPatch, apiDelete } from '@/lib/api/client';
import {
  clusterResponseSchema,
  type ClusterCreate,
  type ClusterResponse,
  type ClusterUpdate,
} from '@/lib/schemas/cluster';

const BASE = '/api/v1/clusters';

export function fetchClusters(): Promise<ClusterResponse[]> {
  return apiFetch(BASE, z.array(clusterResponseSchema));
}

export function createCluster(data: ClusterCreate): Promise<ClusterResponse> {
  return apiPost(BASE, clusterResponseSchema, data);
}

export function updateCluster(id: number, data: ClusterUpdate): Promise<ClusterResponse> {
  return apiPatch(`${BASE}/${id}`, clusterResponseSchema, data);
}

export function deleteCluster(id: number): Promise<void> {
  return apiDelete(`${BASE}/${id}`);
}
