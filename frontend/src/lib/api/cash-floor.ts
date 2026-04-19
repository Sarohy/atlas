import { apiFetch } from '@/lib/api/client';
import { cashFloorResponseSchema, type CashFloorResponse } from '@/lib/schemas/cash-floor';

/**
 * Fetch the Framework 5 cash-floor guidance for a single ticker.
 * Calls GET /api/v1/cash-floor/{ticker}.
 *
 * The backend calls Framework 2 (Regime Modifier) internally to determine the
 * live regime rule; the result reflects the same Brent / VIX snapshot that
 * Framework 2 is using.
 */
export function fetchCashFloor(ticker: string): Promise<CashFloorResponse> {
  return apiFetch(
    `/api/v1/cash-floor/${encodeURIComponent(ticker.toUpperCase())}`,
    cashFloorResponseSchema,
  );
}
