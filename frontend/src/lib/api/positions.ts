import { z } from 'zod';

import { apiFetch, apiPost, apiPatch, apiDelete } from '@/lib/api/client';
import {
  positionResponseSchema,
  tickerSearchResultSchema,
  type PositionResponse,
  type TickerSearchResult,
} from '@/lib/schemas/position';

export function fetchPositions(): Promise<PositionResponse[]> {
  return apiFetch('/api/v1/positions', z.array(positionResponseSchema));
}

export function createPosition(payload: {
  ticker: string;
  company_name: string;
  shares: number | string;
}): Promise<PositionResponse> {
  return apiPost('/api/v1/positions', positionResponseSchema, payload);
}

export function updatePosition(
  id: number,
  payload: { shares: number | string },
): Promise<PositionResponse> {
  return apiPatch(`/api/v1/positions/${id}`, positionResponseSchema, payload);
}

export function deletePosition(id: number): Promise<void> {
  return apiDelete(`/api/v1/positions/${id}`);
}

export function searchTickers(query: string): Promise<TickerSearchResult[]> {
  return apiFetch(
    `/api/v1/tickers/search?q=${encodeURIComponent(query)}`,
    z.array(tickerSearchResultSchema),
  );
}
