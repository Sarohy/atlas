import { apiFetch } from '@/lib/api/client';
import {
  regimeModifierResponseSchema,
  type RegimeModifierResponse,
} from '@/lib/schemas/regime-modifier';

/**
 * Fetch the regime-adjusted conviction score for a single ticker.
 * Calls GET /api/v1/regime-modifier/{ticker}?active_war={bool}[&base_score={n}].
 *
 * When `baseScore` is provided (taken from the Framework 1 React Query cache)
 * the backend skips re-computing the Framework Score, guaranteeing F1 and F2
 * display the same base score at all times.
 */
export function fetchRegimeModifier(
  ticker: string,
  activeWar: boolean,
  baseScore?: number,
): Promise<RegimeModifierResponse> {
  const params = new URLSearchParams({ active_war: String(activeWar) });
  if (baseScore !== undefined) {
    params.set('base_score', String(baseScore));
  }
  return apiFetch(
    `/api/v1/regime-modifier/${encodeURIComponent(ticker.toUpperCase())}?${params.toString()}`,
    regimeModifierResponseSchema,
  );
}
