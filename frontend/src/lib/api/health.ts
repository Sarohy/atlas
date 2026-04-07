import { apiFetch } from './client';
import { healthResponseSchema, type HealthResponse } from '@/lib/schemas/health';

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch('/api/v1/health', healthResponseSchema);
}
