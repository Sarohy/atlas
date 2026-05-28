import { apiFetch } from '@/lib/api/client';
import { optionsFlowResponseSchema, type OptionsFlowResponse } from '@/lib/schemas/options-flow';

/**
 * Fetch the F4 Options Flow analysis for a single ticker from the backend.
 * Calls GET /api/v1/options-flow/{ticker}.
 *
 * `cache: 'no-store'` per F4 v2 spec Q6: the 5-session rolling window must be
 * recomputed on every call.
 */
export function fetchOptionsFlow(ticker: string): Promise<OptionsFlowResponse> {
  return apiFetch(
    `/api/v1/options-flow/${encodeURIComponent(ticker.toUpperCase())}`,
    optionsFlowResponseSchema,
    { cache: 'no-store' },
  );
}
