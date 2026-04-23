import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const f11FloorStatusSchema = z.enum(['COMPLIANT', 'VIOLATED', 'UNKNOWN']);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const gtcItemSchema = z.object({
  ticker: z.string(),
  limit_price: z.number(),
  quantity: z.number(),
  notional_usd: z.number(),
  current_price: z.number().nullable(),
  proximity_pct: z.number().nullable(),
  is_near_money: z.boolean().nullable(),
  is_exempt: z.boolean().nullable(),
  price_missing: z.boolean(),
  price_missing_reason: z.string().nullable(),
});

// ---------------------------------------------------------------------------
// Main result schemas
// ---------------------------------------------------------------------------

export const framework11ResultSchema = z.object({
  // Core floor status
  floor_status: f11FloorStatusSchema,
  floor_violated: z.boolean().nullable(),
  all_buys_blocked: z.boolean(),

  // Regime and floor
  regime: z.string().nullable(),
  floor_pct: z.number().nullable(),
  floor_pct_source: z.string(),
  using_conservative_default: z.boolean(),
  clear_transition_days: z.number().nullable(),

  // Portfolio numbers
  cash_usd: z.number().nullable(),
  cash_pct: z.number().nullable(),
  current_nav: z.number().nullable(),

  // Shortfall / buffer
  shortfall_pct: z.number().nullable(),
  shortfall_usd: z.number().nullable(),
  buffer_pct: z.number().nullable(),
  buffer_usd: z.number().nullable(),

  // GTC aggregate window
  gtc_window_usd: z.number().nullable(),
  gtc_window_negative: z.boolean(),
  gtc_near_money_total_usd: z.number().nullable(),
  gtc_oversubscribed: z.boolean().nullable(),
  gtc_excess_usd: z.number().nullable(),
  gtc_remaining_usd: z.number().nullable(),
  gtc_items: z.array(gtcItemSchema),
  gtc_near_money_count: z.number(),
  gtc_exempt_count: z.number(),
  gtc_price_missing_count: z.number(),

  // Signal queue
  queued_signals_count: z.number(),
  signal_queue: z.array(z.record(z.string(), z.unknown())),

  // Data source health
  f2_available: z.boolean(),
  f30_available: z.boolean(),
  cash_db_available: z.boolean(),
  gtc_db_available: z.boolean(),

  // Metadata
  data_gap_severity: z.string(),
  warning_messages: z.array(z.string()),
  last_updated: z.string(),
  data_age_minutes: z.number(),
  cache_hit: z.boolean(),
});

export const framework11SimpleResultSchema = z.object({
  floor_status: f11FloorStatusSchema,
  floor_violated: z.boolean().nullable(),
  all_buys_blocked: z.boolean(),
  floor_pct: z.number().nullable(),
  cash_pct: z.number().nullable(),
  shortfall_usd: z.number().nullable(),
  gtc_window_usd: z.number().nullable(),
  gtc_oversubscribed: z.boolean().nullable(),
  data_gap_severity: z.string(),
});

export const framework11QueueResponseSchema = z.object({
  queued_signals: z.array(z.record(z.string(), z.unknown())),
  count: z.number(),
});

// ---------------------------------------------------------------------------
// Inferred TypeScript types
// ---------------------------------------------------------------------------

export type F11FloorStatus = z.infer<typeof f11FloorStatusSchema>;
export type GTCItem = z.infer<typeof gtcItemSchema>;
export type Framework11Result = z.infer<typeof framework11ResultSchema>;
export type Framework11SimpleResult = z.infer<typeof framework11SimpleResultSchema>;
export type Framework11QueueResponse = z.infer<typeof framework11QueueResponseSchema>;
