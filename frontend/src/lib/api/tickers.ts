import { z } from 'zod';

import { apiFetch, apiPost, apiPatch, apiDelete } from '@/lib/api/client';
import {
  tickerResponseSchema,
  tickerSearchResultSchema,
  type TickerResponse,
  type TickerSearchResult,
} from '@/lib/schemas/ticker';

export function fetchTickers(): Promise<TickerResponse[]> {
  return apiFetch('/api/v1/tickers', z.array(tickerResponseSchema));
}

export function createTicker(payload: {
  ticker: string;
  company_name: string;
  shares: number | string;
  cluster_id?: number | null;
}): Promise<TickerResponse> {
  return apiPost('/api/v1/tickers', tickerResponseSchema, payload);
}

export function updateTicker(
  id: number,
  payload: { shares: number | string },
): Promise<TickerResponse> {
  return apiPatch(`/api/v1/tickers/${id}`, tickerResponseSchema, payload);
}

export function deleteTicker(id: number): Promise<void> {
  return apiDelete(`/api/v1/tickers/${id}`);
}

export function syncTickers(): Promise<TickerResponse[]> {
  return apiPost('/api/v1/tickers/sync', z.array(tickerResponseSchema), {});
}

export function searchTickers(query: string): Promise<TickerSearchResult[]> {
  return apiFetch(
    `/api/v1/tickers/search?q=${encodeURIComponent(query)}`,
    z.array(tickerSearchResultSchema),
  );
}
