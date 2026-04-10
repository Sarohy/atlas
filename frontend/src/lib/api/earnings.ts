import { apiFetch } from '@/lib/api/client';
import { earningsResponseSchema, type EarningsResponse } from '@/lib/schemas/earnings';

/**
 * Fetch the F2 Earnings Quality analysis for a single ticker from the backend.
 * Calls GET /api/v1/earnings/{ticker}.
 */
export function fetchEarnings(ticker: string): Promise<EarningsResponse> {
  return apiFetch(
    `/api/v1/earnings/${encodeURIComponent(ticker.toUpperCase())}`,
    earningsResponseSchema,
  );
}
