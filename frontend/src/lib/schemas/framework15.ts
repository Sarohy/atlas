import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const f15SeveritySchema = z.enum(['CRITICAL', 'HIGH', 'UNKNOWN']);

export const f15StatusSchema = z.enum([
  'ACTIVE',
  'CLEAR',
  'UNKNOWN',
  'OUTSIDE_HOURS',
]);

export const orderReviewStatusSchema = z.enum([
  'PENDING_REVIEW',
  'KEPT',
  'MODIFIED',
  'CANCELLED',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const pausedOrderSchema = z.object({
  order_id: z.number(),
  ticker: z.string(),
  order_type: z.string(),
  paused_at: z.string(),
  review_status: orderReviewStatusSchema,
});

export const vixSnapshotSchema = z.object({
  current_vix: z.number().nullable(),
  session_open_vix: z.number().nullable(),
  spike_size: z.number().nullable(),
  spike_threshold: z.number().nullable(),
  f15_active: z.boolean().nullable(),
  data_available: z.boolean(),
  market_open: z.boolean(),
  last_updated: z.string(),
});

export const framework15SimpleResultSchema = z.object({
  f15_status: f15StatusSchema,
  f15_active: z.boolean().nullable(),
  severity: f15SeveritySchema.nullable(),
  new_market_orders_blocked: z.boolean(),
  non_stop_orders_paused: z.boolean(),
  data_gap_severity: z.string(),
  market_open: z.boolean(),
});

export const framework15ResultSchema = z.object({
  // Core state
  f15_status: f15StatusSchema,
  f15_active: z.boolean().nullable(),
  severity: f15SeveritySchema.nullable(),

  // VIX data
  current_vix: z.number().nullable(),
  session_open_vix: z.number().nullable(),
  spike_size: z.number().nullable(),
  spike_threshold: z.number().nullable(),

  // Halt state
  halt_triggered_at: z.string().nullable(),
  new_market_orders_blocked: z.boolean(),
  non_stop_orders_paused: z.boolean(),
  limit_orders_flagged: z.boolean(),

  // Paused orders
  paused_orders: z.array(pausedOrderSchema),
  paused_orders_count: z.number(),

  // Override
  override_applied: z.boolean(),
  override_reason: z.string().nullable(),
  override_applied_at: z.string().nullable(),

  // Regime context
  regime_at_trigger: z.string().nullable(),
  regime_available: z.boolean(),

  // Data quality
  polygon_available: z.boolean(),
  f2_available: z.boolean(),
  order_db_available: z.boolean(),
  data_gap_severity: z.string(),

  // Market state
  market_open: z.boolean(),
  session_date: z.string().nullable(),

  // Meta
  last_updated: z.string(),
  cache_hit: z.boolean(),
  warnings: z.array(z.string()),
});

// ---------------------------------------------------------------------------
// Request schemas
// ---------------------------------------------------------------------------

export const addOverrideRequestSchema = z.object({
  override_reason: z.string().min(50),
  restore_order_types: z.array(z.string()),
});

export const reviewOrderRequestSchema = z.object({
  decision: z.string(),
  reviewed_by: z.string(),
});

// ---------------------------------------------------------------------------
// Inferred types
// ---------------------------------------------------------------------------

export type F15Severity = z.infer<typeof f15SeveritySchema>;
export type F15Status = z.infer<typeof f15StatusSchema>;
export type OrderReviewStatus = z.infer<typeof orderReviewStatusSchema>;
export type PausedOrder = z.infer<typeof pausedOrderSchema>;
export type VixSnapshot = z.infer<typeof vixSnapshotSchema>;
export type Framework15SimpleResult = z.infer<
  typeof framework15SimpleResultSchema
>;
export type Framework15Result = z.infer<typeof framework15ResultSchema>;
export type AddOverrideRequest = z.infer<typeof addOverrideRequestSchema>;
export type ReviewOrderRequest = z.infer<typeof reviewOrderRequestSchema>;
