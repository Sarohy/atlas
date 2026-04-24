/**
 * Zod v4 schemas and TypeScript types for Section 16 Exit Rules.
 * All schemas are pure — no imports from hooks or API layer.
 */

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Rule 16.1 — Score-Based Exit
// ---------------------------------------------------------------------------

export const rule161StatusSchema = z.enum([
  'CLEAR',
  'CYCLE_ONE',
  'CYCLE_ONE_PAUSED',
  'CYCLE_TWO',
  'DEFERRED',
  'TRIM_TRIGGERED',
  'FULL_EXIT_TRIGGERED',
  'UNKNOWN',
]);
export type Rule161Status = z.infer<typeof rule161StatusSchema>;

export const rule161ResultSchema = z.object({
  status: rule161StatusSchema,
  cycle_count: z.number().int().min(0).max(2),
  trim_triggered: z.boolean(),
  full_exit_triggered: z.boolean(),
  exit_window_trading_days: z.number().int().nullable(),
  trim_window_trading_days: z.number().int().nullable(),
  trim_pct: z.string().nullable(),
  deferred_reason: z.string().nullable(),
  deferred_until: z.string().nullable(),
  reconciliation_pending: z.boolean(),
  claude_score: z.string().nullable(),
  grok_score: z.string().nullable(),
  score_gap: z.string().nullable(),
  triggering_score: z.string().nullable(),
  triggering_date: z.string().nullable(),
  data_available: z.boolean(),
  missing_sources: z.array(z.string()),
});
export type Rule161Result = z.infer<typeof rule161ResultSchema>;

// ---------------------------------------------------------------------------
// Rule 16.2 — Gap-Down
// ---------------------------------------------------------------------------

export const gapDownStatusSchema = z.enum([
  'CLEAR',
  'HOLDING',
  'RESCORED',
  'RESOLVED',
  'UNKNOWN',
]);
export type GapDownStatus = z.infer<typeof gapDownStatusSchema>;

export const rule162ResultSchema = z.object({
  gap_triggered: z.boolean(),
  status: gapDownStatusSchema,
  gap_down_pct: z.string().nullable(),
  prev_close: z.string().nullable(),
  open_price: z.string().nullable(),
  event_date: z.string().nullable(),
  hold_until: z.string().datetime({ offset: true }).nullable(),
  rescore_at: z.string().datetime({ offset: true }).nullable(),
  rescore_score: z.string().nullable(),
  resolved_at: z.string().datetime({ offset: true }).nullable(),
  data_available: z.boolean(),
  missing_sources: z.array(z.string()),
});
export type Rule162Result = z.infer<typeof rule162ResultSchema>;

// ---------------------------------------------------------------------------
// Rule 16.3 — Appreciation Trim
// ---------------------------------------------------------------------------

export const appreciationStatusSchema = z.enum([
  'CLEAR',
  'NO_NEW_CAPITAL',
  'CONSIDER_TRIM',
  'UNKNOWN',
]);
export type AppreciationStatus = z.infer<typeof appreciationStatusSchema>;

export const rule163ResultSchema = z.object({
  status: appreciationStatusSchema,
  no_new_capital: z.boolean(),
  consider_trim: z.boolean(),
  position_pct_of_nav: z.string().nullable(),
  position_value: z.string().nullable(),
  total_nav: z.string().nullable(),
  trim_pct: z.string().nullable(),
  data_available: z.boolean(),
  missing_sources: z.array(z.string()),
});
export type Rule163Result = z.infer<typeof rule163ResultSchema>;

// ---------------------------------------------------------------------------
// Rule 16.4 — Put Protection
// ---------------------------------------------------------------------------

export const putProtectionStatusSchema = z.enum([
  'PUT_PROTECTION_RECOMMENDED',
  'NOT_TRIGGERED',
  'UNKNOWN',
]);
export type PutProtectionStatus = z.infer<typeof putProtectionStatusSchema>;

export const rule164ConditionDetailSchema = z.object({
  condition_number: z.number().int(),
  description: z.string(),
  met: z.boolean().nullable(),
  value: z.string().nullable(),
  threshold: z.string().nullable(),
});
export type Rule164ConditionDetail = z.infer<typeof rule164ConditionDetailSchema>;

export const rule164ResultSchema = z.object({
  recommend_puts: z.boolean().nullable(),
  status: putProtectionStatusSchema,
  conditions_met: z.number().int(),
  conditions: z.array(rule164ConditionDetailSchema),
  data_available: z.boolean(),
  missing_sources: z.array(z.string()),
});
export type Rule164Result = z.infer<typeof rule164ResultSchema>;

// ---------------------------------------------------------------------------
// Top-level Section 16 result
// ---------------------------------------------------------------------------

export const section16OverallStatusSchema = z.enum([
  'ALL_CLEAR',
  'EXIT_ACTIVE',
  'PARTIAL_DATA',
  'UNKNOWN',
]);
export type Section16OverallStatus = z.infer<typeof section16OverallStatusSchema>;

export const section16ResultSchema = z.object({
  ticker: z.string(),
  available: z.boolean(),
  overall_status: section16OverallStatusSchema,
  rule_161: rule161ResultSchema,
  rule_162: rule162ResultSchema,
  rule_163: rule163ResultSchema,
  rule_164: rule164ResultSchema,
  any_exit_signal: z.boolean(),
  override_active: z.boolean(),
  override_reason: z.string().nullable(),
  override_set_by: z.string().nullable(),
  override_set_at: z.string().datetime({ offset: true }).nullable(),
  evaluated_at: z.string().datetime({ offset: true }),
});
export type Section16Result = z.infer<typeof section16ResultSchema>;

export const activeCycleEntrySchema = z.object({
  ticker: z.string(),
  cycle_status: z.string(),
  cycle_one_date: z.string().nullable(),
  cycle_one_score: z.string().nullable(),
  trim_triggered: z.boolean(),
  full_exit_triggered: z.boolean(),
  deferred_until: z.string().nullable(),
  override_active: z.boolean(),
});
export type ActiveCycleEntry = z.infer<typeof activeCycleEntrySchema>;

export const activeCyclesSummarySchema = z.object({
  cycles: z.array(activeCycleEntrySchema),
  total_active: z.number().int(),
});
export type ActiveCyclesSummary = z.infer<typeof activeCyclesSummarySchema>;

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export type OverrideRequest = {
  reason: string;
  set_by: string;
};

export type GrokScoreRequest = {
  score: number;
  score_date: string;
  entered_by: string;
  notes?: string;
};

export type ResolveGapDownRequest = {
  rescore_score?: number;
  notes?: string;
};
