import { apiFetch } from '@/lib/api/client';
import {
  framework13ResultSchema,
  portfolioBetaResultSchema,
  type Framework13Result,
  type PortfolioBetaResult,
} from '@/lib/schemas/framework13';

/**
 * Fetch Framework 13 beta cap evaluation for a single ticker position.
 *
 * Optionally supply ``positionWeightOverride`` (0.0-1.0 fraction of NAV) for
 * testing — when omitted the backend reads the live portfolio DB.
 */
export function fetchFramework13(
  ticker: string,
  positionWeightOverride?: number,
): Promise<Framework13Result> {
  const params = new URLSearchParams();
  if (positionWeightOverride !== undefined) {
    params.set('position_weight_override', positionWeightOverride.toString());
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch(
    `/api/v1/framework13/${encodeURIComponent(ticker.toUpperCase())}${query}`,
    framework13ResultSchema,
  );
}

/**
 * Fetch the weighted-average and effective portfolio beta across all positions.
 *
 * Optionally supply ``cashPercentageOverride`` (0.0-1.0) for testing.
 */
export function fetchPortfolioBeta(cashPercentageOverride?: number): Promise<PortfolioBetaResult> {
  const params = new URLSearchParams();
  if (cashPercentageOverride !== undefined) {
    params.set('cash_percentage_override', cashPercentageOverride.toString());
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch(`/api/v1/framework13/portfolio/beta${query}`, portfolioBetaResultSchema);
}
