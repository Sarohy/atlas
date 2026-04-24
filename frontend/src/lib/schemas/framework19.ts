import { z } from 'zod';

// ── Status enums ──────────────────────────────────────────────────────────────

export const f19StatusSchema = z.enum(['ACTIVE', 'CLEAR', 'UNKNOWN', 'OUTSIDE_HOURS']);
export const f19SeveritySchema = z.enum(['CRITICAL', 'HIGH', 'UNKNOWN']);
export const orderReviewStatusSchema = z.enum([
  'PENDING_REVIEW',
  'KEPT',
  'MODIFIED',
  'CANCELLED',
]);

// ── Sub-models ────────────────────────────────────────────────────────────────

export const nvdaDropDetailSchema = z.object({
  current_price: z.number().nullable(),
  peak_price_in_window: z.number().nullable(),
  drop_pct: z.number().nullable(),
  drop_amount: z.number().nullable(),
  window_minutes: z.number().nullable(),
  threshold_pct: z.number(),
  threshold_breached: z.boolean(),
});

export const affectedHoldingSchema = z.object({
  ticker: z.string(),
  beta_vs_nvda: z.number().nullable(),
  is_high_beta: z.boolean(),
  market_orders_blocked: z.boolean(),
  buy_orders_paused: z.boolean(),
});

export const f19PausedOrderSchema = z.object({
  order_id: z.number(),
  ticker: z.string(),
  order_type: z.string(),
  beta_vs_nvda: z.number().nullable(),
  is_high_beta: z.boolean().nullable(),
  paused_at: z.string(),
  review_status: orderReviewStatusSchema,
});

// ── Lightweight result for consuming frameworks ───────────────────────────────

export const framework19SimpleResultSchema = z.object({
  f19_status: f19StatusSchema,
  f19_active: z.boolean().nullable(),
  all_ai_buys_blocked: z.boolean(),
  high_beta_market_orders_blocked: z.boolean(),
  beta_threshold: z.number().nullable(),
  drop_pct: z.number().nullable(),
  threshold_pct: z.number().nullable(),
  polygon_available: z.boolean(),
  data_gap_severity: z.string(),
  market_open: z.boolean(),
});

// ── Full evaluation result ────────────────────────────────────────────────────

export const framework19ResultSchema = z.object({
  f19_status: f19StatusSchema,
  f19_active: z.boolean().nullable(),
  severity: f19SeveritySchema.nullable(),
  nvda_drop: nvdaDropDetailSchema,
  market_open: z.boolean(),
  session_date: z.string(),
  triggered_at: z.string().nullable(),
  all_ai_buys_blocked: z.boolean(),
  high_beta_market_orders_blocked: z.boolean(),
  beta_threshold: z.number().nullable(),
  affected_holdings: z.array(affectedHoldingSchema),
  paused_orders_count: z.number(),
  paused_orders: z.array(f19PausedOrderSchema),
  regime: z.string().nullable(),
  regime_available: z.boolean(),
  polygon_available: z.boolean(),
  alert_sent: z.boolean(),
  alert_sent_at: z.string().nullable(),
  data_gap_severity: z.string(),
  warning_messages: z.array(z.string()),
  last_updated: z.string(),
});

export const reviewOrderRequestSchema = z.object({
  decision: z.enum(['KEPT', 'MODIFIED', 'CANCELLED']),
  reviewed_by: z.string().min(1).max(100),
});

// ── TypeScript types ──────────────────────────────────────────────────────────

export type F19Status = z.infer<typeof f19StatusSchema>;
export type F19Severity = z.infer<typeof f19SeveritySchema>;
export type OrderReviewStatus = z.infer<typeof orderReviewStatusSchema>;
export type NVDADropDetail = z.infer<typeof nvdaDropDetailSchema>;
export type AffectedHolding = z.infer<typeof affectedHoldingSchema>;
export type F19PausedOrder = z.infer<typeof f19PausedOrderSchema>;
export type Framework19SimpleResult = z.infer<typeof framework19SimpleResultSchema>;
export type Framework19Result = z.infer<typeof framework19ResultSchema>;
export type ReviewOrderRequest = z.infer<typeof reviewOrderRequestSchema>;
