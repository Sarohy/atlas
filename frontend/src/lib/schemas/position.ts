import { z } from 'zod';

export const tickerSearchResultSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  market: z.string(),
  type: z.string(),
});

export const positionSchema = z.object({
  ticker: z.string().min(1).max(20),
  company_name: z.string().min(1),
  shares: z.coerce.number().gt(0),
});

export const positionUpdateSchema = z.object({
  shares: z.coerce.number().gt(0),
});

export const positionResponseSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  company_name: z.string(),
  shares: z.coerce.number(),
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
export type Position = z.infer<typeof positionSchema>;
export type PositionUpdate = z.infer<typeof positionUpdateSchema>;
export type PositionResponse = z.infer<typeof positionResponseSchema>;
