import { apiFetch } from '@/lib/api/client';
import { momentumResponseSchema, type MomentumResponse } from '@/lib/schemas/momentum';

/**
 * Fetch the F1 Momentum analysis for a single ticker from the backend.
 * Calls GET /api/v1/momentum/{ticker}.
 */
export function fetchMomentum(ticker: string): Promise<MomentumResponse> {
  return apiFetch(
    `/api/v1/momentum/${encodeURIComponent(ticker.toUpperCase())}`,
    momentumResponseSchema,
  );
}
