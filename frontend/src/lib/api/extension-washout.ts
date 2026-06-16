import { apiFetch } from '@/lib/api/client';
import {
  extensionWashoutResponseSchema,
  type ExtensionWashoutResponse,
} from '@/lib/schemas/extension-washout';

/**
 * Fetch the Extension & Washout Overlay for a single ticker.
 * Calls GET /api/v1/extension-washout/{ticker}[?position_weight_pct=&negative_catalyst=].
 */
export function fetchExtensionWashout(
  ticker: string,
  positionWeightPct?: number | null,
  negativeCatalyst = false,
  beta?: number | null,
): Promise<ExtensionWashoutResponse> {
  const params = new URLSearchParams();
  if (positionWeightPct != null) params.set('position_weight_pct', String(positionWeightPct));
  if (negativeCatalyst) params.set('negative_catalyst', 'true');
  if (beta != null) params.set('beta', String(beta));
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch(
    `/api/v1/extension-washout/${encodeURIComponent(ticker.toUpperCase())}${query}`,
    extensionWashoutResponseSchema,
  );
}
