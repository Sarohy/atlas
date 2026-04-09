import { apiFetch } from '@/lib/api/client';
import { optionsFlowResponseSchema, type OptionsFlowResponse } from '@/lib/schemas/options-flow';

/**
 * Fetch the F4 Options Flow analysis for a single ticker from the backend.
 * Calls GET /api/v1/options-flow/{ticker}.
 */
export function fetchOptionsFlow(ticker: string): Promise<OptionsFlowResponse> {
  return apiFetch(
    `/api/v1/options-flow/${encodeURIComponent(ticker.toUpperCase())}`,
    optionsFlowResponseSchema,
  );
}
