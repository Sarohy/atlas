import { apiFetch } from '@/lib/api/client';
import {
  convictionActionResponseSchema,
  type ConvictionActionResponse,
} from '@/lib/schemas/conviction-action';

/**
 * Fetch the Framework 6 conviction-action guidance for a single ticker.
 * Calls GET /api/v1/conviction-action/{ticker}[?adjusted_score={n}].
 *
 * When `adjustedScore` is supplied (the score already displayed by the F1
 * panel — i.e. `final_score + regime_modifier`, clamped 0-100) the backend
 * skips the regime service entirely and maps that value directly to a tier.
 * This prevents the regime delta from being applied twice.
 */
export function fetchConvictionAction(
  ticker: string,
  adjustedScore?: number,
): Promise<ConvictionActionResponse> {
  const params = new URLSearchParams();
  if (adjustedScore !== undefined) {
    params.set('adjusted_score', String(adjustedScore));
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch(
    `/api/v1/conviction-action/${encodeURIComponent(ticker.toUpperCase())}${query}`,
    convictionActionResponseSchema,
  );
}
