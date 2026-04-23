import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const drawdownStateSchema = z.enum([
  'NORMAL',
  'CARVEOUT',
  'HARD_HALT',
  'UNKNOWN',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const positionNavItemSchema = z.object({
  ticker: z.string(),
  shares: z.number().nullable(),
  price: z.number().nullable(),
  price_stale: z.boolean(),
  price_age_min: z.number().nullable(),
  value_usd: z.number().nullable(),
  excluded: z.boolean(),
  exclude_reason: z.string().nullable(),
});

// ---------------------------------------------------------------------------
// Main result schemas
// ---------------------------------------------------------------------------

export const framework30ResultSchema = z.object({
  current_nav: z.number().nullable(),
  peak_nav_90d: z.number().nullable(),
  peak_nav_date: z.string().nullable(),
  drawdown_pct: z.number().nullable(),
  drawdown_usd: z.number().nullable(),
  drawdown_state: drawdownStateSchema,

  adds_permitted: z.boolean(),
  leaps_permitted: z.boolean(),
  leaps_position_cap_pct: z.number().nullable(),
  all_signals_halted: z.boolean(),
  hard_halt_active: z.boolean(),
  limit_orders_cancel: z.boolean(),

  recovery_active: z.boolean().nullable(),
  recovery_start_date: z.string().nullable(),
  recovery_days_elapsed: z.number().nullable(),
  recovery_days_remaining: z.number().nullable(),
  sizing_multiplier: z.number().nullable(),

  position_nav_items: z.array(positionNavItemSchema),
  stale_positions: z.array(z.string()),
  missing_positions: z.array(z.string()),

  nav_data_complete: z.boolean(),
  peak_data_source: z.string(),
  data_age_minutes: z.number(),
  warning_messages: z.array(z.string()),
  cache_hit: z.boolean(),
});

export const framework30DrawdownStateSchema = z.object({
  drawdown_state: drawdownStateSchema,
  drawdown_pct: z.number().nullable(),
  adds_permitted: z.boolean(),
  leaps_permitted: z.boolean(),
  leaps_position_cap_pct: z.number().nullable(),
  sizing_multiplier: z.number().nullable(),
  hard_halt_active: z.boolean(),
  data_complete: z.boolean(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type DrawdownState = z.infer<typeof drawdownStateSchema>;
export type PositionNavItem = z.infer<typeof positionNavItemSchema>;
export type Framework30Result = z.infer<typeof framework30ResultSchema>;
export type Framework30DrawdownState = z.infer<typeof framework30DrawdownStateSchema>;
