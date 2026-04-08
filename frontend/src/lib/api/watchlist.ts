import { z } from 'zod';

import { apiFetch, apiPost, apiDelete } from '@/lib/api/client';
import { watchlistItemResponseSchema, type WatchlistItemResponse } from '@/lib/schemas/watchlist';

export function fetchWatchlist(): Promise<WatchlistItemResponse[]> {
  return apiFetch('/api/v1/watchlist', z.array(watchlistItemResponseSchema));
}

export function addToWatchlist(payload: {
  ticker: string;
  company_name: string;
}): Promise<WatchlistItemResponse> {
  return apiPost('/api/v1/watchlist', watchlistItemResponseSchema, payload);
}

export function removeFromWatchlist(id: number): Promise<void> {
  return apiDelete(`/api/v1/watchlist/${id}`);
}

export function syncWatchlist(): Promise<WatchlistItemResponse[]> {
  return apiPost('/api/v1/watchlist/sync', z.array(watchlistItemResponseSchema), {});
}
