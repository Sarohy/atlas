import { apiFetch } from '@/lib/api/client';
import {
  regimeModifierResponseSchema,
  type RegimeModifierResponse,
} from '@/lib/schemas/regime-modifier';

/**
 * Fetch the regime-adjusted conviction score for a single ticker.
 * Calls GET /api/v1/regime-modifier/{ticker}?active_war={bool}.
 *
 * Fetches live Brent crude + VIX data from Polygon.io, retrieves the base
 * Framework Score, then applies whichever of the three market-regime rules
 * fires first (Rule 1 Crisis / Rule 2 Caution / Rule 3 Clear).
 */
export function fetchRegimeModifier(
  ticker: string,
  activeWar: boolean,
): Promise<RegimeModifierResponse> {
  const params = new URLSearchParams({ active_war: String(activeWar) });
  return apiFetch(
    `/api/v1/regime-modifier/${encodeURIComponent(ticker.toUpperCase())}?${params.toString()}`,
    regimeModifierResponseSchema,
  );
}
