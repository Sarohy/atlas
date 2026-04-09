import { apiFetch } from '@/lib/api/client';
import { fundamentalResponseSchema, type FundamentalResponse } from '@/lib/schemas/fundamental';

/**
 * Fetch the F5 Fundamental Quality analysis for a single ticker from the backend.
 * Calls GET /api/v1/fundamental/{ticker}.
 */
export function fetchFundamental(ticker: string): Promise<FundamentalResponse> {
  return apiFetch(
    `/api/v1/fundamental/${encodeURIComponent(ticker.toUpperCase())}`,
    fundamentalResponseSchema,
  );
}
