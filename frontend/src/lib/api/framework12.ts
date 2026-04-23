import { apiFetch } from '@/lib/api/client';
import {
  catalystResponseSchema,
  framework12PortfolioSummarySchema,
  framework12ResultSchema,
  framework12StatusResultSchema,
  type AddCatalystRequest,
  type AddOverrideRequest,
  type CatalystResponse,
  type Framework12PortfolioSummary,
  type Framework12Result,
  type Framework12StatusResult,
} from '@/lib/schemas/framework12';

/**
 * Fetch the full Framework 12 no-fly zone evaluation for one ticker.
 * Calls GET /api/v1/framework12/{ticker}.
 */
export function fetchFramework12(ticker: string): Promise<Framework12Result> {
  return apiFetch(
    `/api/v1/framework12/${encodeURIComponent(ticker)}`,
    framework12ResultSchema,
  );
}

/**
 * Fetch the lightweight no-fly status for one ticker.
 * Calls GET /api/v1/framework12/{ticker}/status.
 */
export function fetchFramework12Status(
  ticker: string,
): Promise<Framework12StatusResult> {
  return apiFetch(
    `/api/v1/framework12/${encodeURIComponent(ticker)}/status`,
    framework12StatusResultSchema,
  );
}

/**
 * Fetch the portfolio-level Framework 12 summary.
 * Calls GET /api/v1/framework12/portfolio/summary.
 */
export function fetchFramework12PortfolioSummary(): Promise<Framework12PortfolioSummary> {
  return apiFetch(
    '/api/v1/framework12/portfolio/summary',
    framework12PortfolioSummarySchema,
  );
}

/**
 * Add a non-earnings catalyst event.
 * Calls POST /api/v1/framework12/catalysts.
 */
export function addCatalyst(
  body: AddCatalystRequest,
): Promise<CatalystResponse> {
  return apiFetch('/api/v1/framework12/catalysts', catalystResponseSchema, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Deactivate a catalyst event after it has passed.
 * Calls PUT /api/v1/framework12/catalysts/{id}/deactivate.
 */
export function deactivateCatalyst(id: number): Promise<CatalystResponse> {
  return apiFetch(
    `/api/v1/framework12/catalysts/${id}/deactivate`,
    catalystResponseSchema,
    { method: 'PUT' },
  );
}

/**
 * Apply a human override for one blocked action.
 * Calls POST /api/v1/framework12/{ticker}/override.
 */
export function addOverride(
  ticker: string,
  body: AddOverrideRequest,
): Promise<CatalystResponse> {
  return apiFetch(
    `/api/v1/framework12/${encodeURIComponent(ticker)}/override`,
    catalystResponseSchema,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
}

/**
 * Invalidate cache and re-evaluate one ticker.
 * Calls POST /api/v1/framework12/refresh/{ticker}.
 */
export function refreshFramework12(
  ticker: string,
): Promise<Framework12Result> {
  return apiFetch(
    `/api/v1/framework12/refresh/${encodeURIComponent(ticker)}`,
    framework12ResultSchema,
    { method: 'POST' },
  );
}
