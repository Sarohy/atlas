import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const ivAlertSchema = z.enum([
  'NONE',
  'IV_HIGH_ALERT',
  'IV_COMPRESSION_SIGNAL',
  'IV_EARNINGS_PROXIMITY',
  'DATA_UNAVAILABLE',
]);

export const entryConditionStatusSchema = z.enum([
  'CONFIRMED',
  'NOT_MET',
  'INCOMPLETE',
  'NOT_APPLICABLE',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const entryConditionSchema = z.object({
  condition_name: z.string(),
  status: entryConditionStatusSchema,
  met: z.boolean().nullable(),
  detail: z.string().nullable(),
});

// ---------------------------------------------------------------------------
// Main result schemas
// ---------------------------------------------------------------------------

export const leapsEligibilitySchema = z.object({
  ticker: z.string(),
  leaps_eligible: z.boolean().nullable(),
  eligibility_undetermined: z.boolean(),

  score: z.number().nullable(),
  tier: z.string().nullable(),
  flow_confirmed: z.boolean().nullable(),

  regime_state: z.string().nullable(),
  regime_clears_leaps: z.boolean().nullable(),

  gate_f7_active: z.boolean().nullable(),
  gate_f29_passed: z.boolean().nullable(),
  gate_f30_permits_leaps: z.boolean().nullable(),

  iv_current: z.number().nullable(),
  iv_percentile: z.number().nullable(),
  iv_blocked: z.boolean().nullable(),
  iv_alert: ivAlertSchema,

  entry_conditions: z.array(entryConditionSchema),
  conditions_met: z.number().int(),
  conditions_required: z.number().int(),

  block_reasons: z.array(z.string()),
  warning_messages: z.array(z.string()),

  data_age_minutes: z.number(),
  cache_hit: z.boolean(),
});

export const leapsPositionSchema = z.object({
  id: z.number().int(),
  ticker: z.string(),
  option_symbol: z.string(),
  expiration_date: z.string(),
  strike_price: z.number(),
  option_type: z.string(),
  contracts: z.number().int(),
  entry_price: z.number(),
  current_price: z.number().nullable(),
  current_value: z.number().nullable(),
  theta_daily: z.number().nullable(),
  iv_at_entry: z.number().nullable(),
  iv_current: z.number().nullable(),
  pnl_usd: z.number().nullable(),
  pnl_pct: z.number().nullable(),
  days_to_expiry: z.number().nullable(),
  status: z.string(),
  notes: z.string().nullable(),
});

export const leapsBucketStatusSchema = z.object({
  total_deployed_usd: z.number(),
  total_deployed_pct: z.number(),
  total_cap_pct: z.number(),
  positions_count: z.number().int(),
  bucket_available_pct: z.number(),
  bucket_available_usd: z.number().nullable(),
  warning_messages: z.array(z.string()),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type IVAlert = z.infer<typeof ivAlertSchema>;
export type EntryConditionStatus = z.infer<typeof entryConditionStatusSchema>;
export type EntryCondition = z.infer<typeof entryConditionSchema>;
export type LeapsEligibility = z.infer<typeof leapsEligibilitySchema>;
export type LeapsPosition = z.infer<typeof leapsPositionSchema>;
export type LeapsBucketStatus = z.infer<typeof leapsBucketStatusSchema>;
