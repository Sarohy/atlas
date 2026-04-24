import { z } from 'zod';

// ── Status enum ──────────────────────────────────────────────────────────────
export const f18StatusSchema = z.enum(['ACTIVE', 'CLEAR', 'UNKNOWN']);

// ── Actions (only present when f18_active = true) ────────────────────────────
export const framework18ActionsSchema = z.object({
  reduce_aggressive_adds: z.boolean(),
  add_reduction_pct: z.number(),
  prioritize_quality_only: z.boolean(),
  min_tier_for_new_adds: z.string(),
  no_speculative_starters: z.boolean(),
  tier3_adds_blocked: z.boolean(),
});

// ── Lightweight result (for consuming frameworks) ────────────────────────────
export const framework18SimpleResultSchema = z.object({
  f18_status: f18StatusSchema,
  f18_active: z.boolean().nullable(),
  consecutive_weeks_down: z.number().nullable(),
  consecutive_threshold: z.number().nullable(),
  add_reduction_pct: z.number().nullable(),
  no_speculative_starters: z.boolean(),
  tier3_adds_blocked: z.boolean(),
  data_gap_severity: z.string(),
  spy_data_available: z.boolean(),
});

// ── Full result ───────────────────────────────────────────────────────────────
export const framework18ResultSchema = z.object({
  f18_status: f18StatusSchema,
  f18_active: z.boolean().nullable(),
  consecutive_weeks_down: z.number().nullable(),
  consecutive_threshold: z.number().nullable(),
  add_reduction_pct: z.number().nullable(),
  weeks_fetched: z.number().nullable(),
  spy_weekly_closes: z.array(z.number()),
  candle_dates: z.array(z.string()),
  spy_data_available: z.boolean(),
  spy_data_stale: z.boolean(),
  polygon_available: z.boolean(),
  actions: framework18ActionsSchema.nullable(),
  factor9_contribution: z.string().nullable(),
  data_gap_severity: z.string(),
  warning_messages: z.array(z.string()),
  last_updated: z.string(),
  cache_hit: z.boolean(),
});

// ── TypeScript types ──────────────────────────────────────────────────────────
export type F18Status = z.infer<typeof f18StatusSchema>;
export type Framework18Actions = z.infer<typeof framework18ActionsSchema>;
export type Framework18SimpleResult = z.infer<typeof framework18SimpleResultSchema>;
export type Framework18Result = z.infer<typeof framework18ResultSchema>;
