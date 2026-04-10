import { apiFetch } from '@/lib/api/client';
import { analystResponseSchema, type AnalystResponse } from '@/lib/schemas/analyst';

/**
 * Fetch the F3 Analyst Conviction analysis for a single ticker from the backend.
 * Calls GET /api/v1/analyst/{ticker}.
 */
export function fetchAnalyst(ticker: string): Promise<AnalystResponse> {
  return apiFetch(
    `/api/v1/analyst/${encodeURIComponent(ticker.toUpperCase())}`,
    analystResponseSchema,
  );
}
