import { apiFetch } from '@/lib/api/client';
import { framework8ResponseSchema, type Framework8Response } from '@/lib/schemas/framework8';

/**
 * Fetch the Framework 8 insider activity analysis for a single ticker.
 * Calls GET /api/v1/framework8/{ticker}.
 *
 * Hardcoded tickers (NBIS, CRDO, FN, COHR, CF) are always available without
 * a live API key. All other tickers are fetched from the SEC EDGAR feed.
 */
export function fetchFramework8(ticker: string): Promise<Framework8Response> {
  return apiFetch(
    `/api/v1/framework8/${encodeURIComponent(ticker.toUpperCase())}`,
    framework8ResponseSchema,
  );
}
