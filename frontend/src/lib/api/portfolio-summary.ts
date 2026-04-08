import { apiFetch, apiPut } from './client';
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
