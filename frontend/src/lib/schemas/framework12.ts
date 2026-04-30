import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const framework12StatusSchema = z.enum([
  'SIZED',
  'WATCHLIST',
  'BLOCKED',
  'UNKNOWN',
]);
export type Framework12Status = z.infer<typeof framework12StatusSchema>;

// ---------------------------------------------------------------------------
// Decision matrix row
// ---------------------------------------------------------------------------

export const decisionMatrixRowSchema = z.object({
  priority_code: z.string(),
  priority_label: z.string(),
  track: z.string().nullable(),
  earnings_max_days: z.number().nullable(),
  earnings_min_days: z.number().nullable(),
  override_required: z.boolean(),
  underweight_required: z.boolean(),
  strong_flow_required: z.boolean(),
  size_min_pct: z.number(),
  size_max_pct: z.number(),
  timing_rule: z.string(),
  is_watchlist_only: z.boolean(),
  priority_order: z.number(),
  active: z.boolean(),
});
export type DecisionMatrixRow = z.infer<typeof decisionMatrixRowSchema>;

// ---------------------------------------------------------------------------
// Top-level result
// ---------------------------------------------------------------------------

export const framework12ResultSchema = z.object({
  ticker: z.string(),
  status: framework12StatusSchema,
  matched_row: decisionMatrixRowSchema.nullable(),
  current_nav_usd: z.number().nullable(),
  size_min_usd: z.number().nullable(),
  size_max_usd: z.number().nullable(),
  timing_rule: z.string().nullable(),
  blocked_reason: z.string().nullable(),
  evaluated_at: z.string(),
});
export type Framework12Result = z.infer<typeof framework12ResultSchema>;

export const framework12SizingSchema = z.object({
  ticker: z.string(),
  status: framework12StatusSchema,
  priority_code: z.string().nullable(),
  size_min_usd: z.number().nullable(),
  size_max_usd: z.number().nullable(),
  timing_rule: z.string().nullable(),
  current_nav_usd: z.number().nullable(),
  blocked_reason: z.string().nullable(),
});
export type Framework12Sizing = z.infer<typeof framework12SizingSchema>;
