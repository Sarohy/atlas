import { z } from 'zod';

export const tickerSearchResultSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  market: z.string(),
  type: z.string(),
});

export const tickerSchema = z.object({
  ticker: z.string().min(1).max(20),
  company_name: z.string().min(1),
  shares: z.coerce.number().gt(0),
  /** Optional cluster assignment at creation time. */
  cluster_id: z.number().nullable().optional(),
});

export const tickerUpdateSchema = z.object({
  shares: z.coerce.number().gt(0),
  cluster_id: z.number().nullable().optional(),
});

export const tickerResponseSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  company_name: z.string(),
  shares: z.coerce.number(),
  // Cluster assignment — null/undefined if unassigned
  cluster_id: z.number().nullable().optional(),
  // Market-data fields — null/undefined until first sync
  current_price: z.coerce.number().nullable().optional(),
  previous_close: z.coerce.number().nullable().optional(),
  day_change: z.coerce.number().nullable().optional(),
  day_change_pct: z.coerce.number().nullable().optional(),
  position_value: z.coerce.number().nullable().optional(),
  beta: z.coerce.number().nullable().optional(),
  synced_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type TickerSearchResult = z.infer<typeof tickerSearchResultSchema>;
export type Ticker = z.infer<typeof tickerSchema>;
export type TickerUpdate = z.infer<typeof tickerUpdateSchema>;
export type TickerResponse = z.infer<typeof tickerResponseSchema>;
