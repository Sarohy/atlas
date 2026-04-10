import { apiFetch } from '@/lib/api/client';
import { marketConditionsSchema, type MarketConditions } from '@/lib/schemas/market-conditions';

/**
 * Fetch current Brent crude and VIX values.
 * Calls GET /api/v1/market/conditions — ticker-independent.
 */
export function fetchMarketConditions(): Promise<MarketConditions> {
  return apiFetch('/api/v1/market/conditions', marketConditionsSchema);
}
