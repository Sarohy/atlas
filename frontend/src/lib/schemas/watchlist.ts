import { z } from 'zod';

export const watchlistItemResponseSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  company_name: z.string(),
  current_price: z.coerce.number().nullable().optional(),
  previous_close: z.coerce.number().nullable().optional(),
  day_change: z.coerce.number().nullable().optional(),
  day_change_pct: z.coerce.number().nullable().optional(),
  beta: z.coerce.number().nullable().optional(),
  synced_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type WatchlistItemResponse = z.infer<typeof watchlistItemResponseSchema>;
