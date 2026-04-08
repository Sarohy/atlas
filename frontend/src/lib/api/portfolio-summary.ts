import { apiFetch, apiPost, apiPut } from './client';
import {
  cashResponseSchema,
  portfolioSummarySchema,
  type CashResponse,
  type CashUpdate,
  type PortfolioSummary,
} from '@/lib/schemas/portfolio-summary';

const BASE = '/api/v1/portfolio';

export function fetchPortfolioSummary(): Promise<PortfolioSummary> {
  return apiFetch(`${BASE}/summary`, portfolioSummarySchema);
}

export function fetchCash(): Promise<CashResponse> {
  return apiFetch(`${BASE}/cash`, cashResponseSchema);
}

export function updateCash(data: CashUpdate): Promise<CashResponse> {
  return apiPut(`${BASE}/cash`, cashResponseSchema, data);
}

/**
 * Add or subtract `delta` from the portfolio cash balance.
 * Positive = deposit; negative = withdrawal.
 * The backend clamps the result at zero — it cannot go negative.
 */
export function adjustCash(delta: number): Promise<CashResponse> {
  return apiPost(`${BASE}/cash/adjust`, cashResponseSchema, { delta });
}
