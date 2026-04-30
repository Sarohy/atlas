import { apiFetch } from '@/lib/api/client';
import {
  cashFloorResponseSchema,
  framework5ResponseSchema,
  type CashFloorResponse,
  type Framework5Response,
} from '@/lib/schemas/cash-floor';

/**
 * Fetch the Framework 5 portfolio-level cash floor status.
 * Calls GET /api/v1/cash-floor/status.
 *
 * No ticker required — regime and portfolio data are read server-side.
 */
export function fetchFramework5Status(): Promise<Framework5Response> {
  return apiFetch('/api/v1/cash-floor/status', framework5ResponseSchema);
}

/**
 * Fetch Framework 5 cash-floor guidance for a single ticker (legacy).
 * Calls GET /api/v1/cash-floor/{ticker}.
 */
export function fetchCashFloor(ticker: string): Promise<CashFloorResponse> {
  return apiFetch(
    `/api/v1/cash-floor/${encodeURIComponent(ticker.toUpperCase())}`,
    cashFloorResponseSchema,
  );
}
