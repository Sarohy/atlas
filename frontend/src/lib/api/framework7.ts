import { apiFetch } from '@/lib/api/client';
import { earningsGateSchema, type EarningsGate } from '@/lib/schemas/framework7';

/**
 * Fetch the Framework 7 Earnings Gate evaluation for a single ticker.
 * Calls GET /api/v1/framework7/{ticker}[?score={n}].
 *
 * When `score` is supplied (the regime-adjusted F1 display score) the backend
 * uses it directly and skips its own F1 re-fetch — ensuring the gate evaluates
 * the exact same score the investor sees on the Framework 1 panel.
 */
export function fetchFramework7(ticker: string, score?: number): Promise<EarningsGate> {
  const params = new URLSearchParams();
  if (score !== undefined) {
    params.set('score', String(score));
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiFetch(
    `/api/v1/framework7/${encodeURIComponent(ticker.toUpperCase())}${query}`,
    earningsGateSchema,
  );
}
