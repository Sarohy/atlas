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
  created_at: z.string(),
  updated_at: z.string(),
});

export type TickerSearchResult = z.infer<typeof tickerSearchResultSchema>;
export type Position = z.infer<typeof positionSchema>;
export type PositionUpdate = z.infer<typeof positionUpdateSchema>;
export type PositionResponse = z.infer<typeof positionResponseSchema>;
