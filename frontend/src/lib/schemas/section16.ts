import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const trackTypeSchema = z.enum(['TRACK_A', 'TRACK_B', 'UNASSIGNED']);
export type TrackType = z.infer<typeof trackTypeSchema>;

export const gateResultSchema = z.enum(['PASS', 'FAIL', 'UNKNOWN']);
export type GateResult = z.infer<typeof gateResultSchema>;

export const rule1PrioritySchema = z.enum([
  'PRIORITY_1',
  'PRIORITY_2',
  'PRIORITY_3',
  'NO_MATCH',
]);
export type Rule1Priority = z.infer<typeof rule1PrioritySchema>;

// ---------------------------------------------------------------------------
// Per-rule result schemas
// ---------------------------------------------------------------------------

export const rule1ResultSchema = z.object({
  result: gateResultSchema,
  priority_matched: rule1PrioritySchema,
  dark_pool_usd: z.number().nullable(),
  flow_usd: z.number().nullable(),
  days_to_earnings: z.number().nullable(),
  threshold_dark_pool_usd: z.number().nullable(),
  threshold_flow_usd: z.number().nullable(),
  reason: z.string(),
});
export type Rule1Result = z.infer<typeof rule1ResultSchema>;

export const rule2ResultSchema = z.object({
  result: gateResultSchema,
  days_to_earnings: z.number().nullable(),
  earnings_date: z.string().nullable(),
  catalyst_max_days: z.number(),
  parabolic_window: z.boolean(),
  reason: z.string(),
});
export type Rule2Result = z.infer<typeof rule2ResultSchema>;

export const rule3ResultSchema = z.object({
  result: gateResultSchema,
  current_price: z.number().nullable(),
  high_365d: z.number().nullable(),
  pct_below_high: z.number().nullable(),
  near_high_pct_threshold: z.number(),
  pullback_pct_required: z.number(),
  pullback_pct_actual: z.number().nullable(),
  reason: z.string(),
});
export type Rule3Result = z.infer<typeof rule3ResultSchema>;

export const rule4ResultSchema = z.object({
  result: gateResultSchema,
  fit_date: z.string().nullable(),
  fits_portfolio: z.boolean().nullable(),
  set_by: z.string().nullable(),
  cluster_gap: z.string().nullable(),
  redundancy_check: z.string().nullable(),
  reason: z.string(),
});
export type Rule4Result = z.infer<typeof rule4ResultSchema>;

export const overrideResultSchema = z.object({
  available: z.boolean(),
  used_in_cycle: z.boolean(),
  qualifies: z.boolean(),
  dark_pool_usd: z.number().nullable(),
  flow_usd: z.number().nullable(),
  threshold_dark_pool_usd: z.number(),
  threshold_flow_usd: z.number(),
  lookback_days: z.number(),
  reason: z.string(),
});
export type OverrideResult = z.infer<typeof overrideResultSchema>;

// ---------------------------------------------------------------------------
// Top-level result
// ---------------------------------------------------------------------------

export const section16ResultSchema = z.object({
  ticker: z.string(),
  track: trackTypeSchema,
  gate: gateResultSchema,
  rule1: rule1ResultSchema.nullable(),
  rule2: rule2ResultSchema.nullable(),
  rule3: rule3ResultSchema.nullable(),
  rule4: rule4ResultSchema.nullable(),
  override: overrideResultSchema.nullable(),
  override_used: z.boolean(),
  evaluated_at: z.string(),
  notes: z.string().nullable(),
});
export type Section16Result = z.infer<typeof section16ResultSchema>;

export const section16GateSchema = z.object({
  ticker: z.string(),
  track: trackTypeSchema,
  gate: gateResultSchema,
  override_used: z.boolean(),
});
export type Section16Gate = z.infer<typeof section16GateSchema>;

// ---------------------------------------------------------------------------
// Mutation request bodies
// ---------------------------------------------------------------------------

export const trackAssignmentRequestSchema = z.object({
  track: z.enum(['TRACK_A', 'TRACK_B']),
  assigned_by: z.string().min(1).max(100),
  notes: z.string().nullable().optional(),
});
export type TrackAssignmentRequest = z.infer<typeof trackAssignmentRequestSchema>;

export const trackAssignmentResponseSchema = z.object({
  ticker: z.string(),
  track: z.string(),
  assigned_by: z.string(),
  notes: z.string().nullable(),
});
export type TrackAssignmentResponse = z.infer<typeof trackAssignmentResponseSchema>;

export const rule4RequestSchema = z.object({
  fits_portfolio: z.boolean(),
  set_by: z.string().min(1).max(100),
  cluster_gap: z.string().nullable().optional(),
  redundancy_check: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});
export type Rule4Request = z.infer<typeof rule4RequestSchema>;

export const rule4ResponseSchema = z.object({
  ticker: z.string(),
  fit_date: z.string(),
  fits_portfolio: z.boolean(),
  set_by: z.string(),
});
export type Rule4Response = z.infer<typeof rule4ResponseSchema>;

export const overrideUseRequestSchema = z.object({
  used_by: z.string().min(1).max(100),
  notes: z.string().nullable().optional(),
});
export type OverrideUseRequest = z.infer<typeof overrideUseRequestSchema>;

export const overrideUseResponseSchema = z.object({
  ticker: z.string(),
  earnings_cycle_start: z.string(),
  earnings_cycle_end: z.string(),
  override_used: z.boolean(),
  override_used_by: z.string(),
});
export type OverrideUseResponse = z.infer<typeof overrideUseResponseSchema>;
