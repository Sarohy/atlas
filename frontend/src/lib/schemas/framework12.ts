import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const catalystTypeSchema = z.enum([
  'EARNINGS',
  'INDEX_INCLUSION',
  'PRODUCT_LAUNCH',
  'PARTNERSHIP',
  'ACQUISITION',
  'OTHER',
]);

export const noFlyStatusSchema = z.enum(['ACTIVE', 'CLEAR', 'UNKNOWN']);

export const actionStatusSchema = z.enum([
  'BLOCKED',
  'PERMITTED',
  'OVERRIDDEN',
  'UNKNOWN',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const activeCatalystSchema = z.object({
  catalyst_type: catalystTypeSchema,
  catalyst_date: z.string(),
  days_to_catalyst: z.number(),
  description: z.string().nullable(),
  source: z.string(),
});

export const overrideDetailSchema = z.object({
  action_type: z.string(),
  override_reason: z.string(),
  entered_by: z.string().nullable(),
  created_at: z.string(),
  override_expires_at: z.string(),
});

// ---------------------------------------------------------------------------
// Main result schemas
// ---------------------------------------------------------------------------

export const framework12ResultSchema = z.object({
  ticker: z.string(),

  // Core no-fly state
  no_fly_status: noFlyStatusSchema,
  no_fly_active: z.boolean().nullable(),

  // Catalysts in window
  active_catalysts: z.array(activeCatalystSchema),
  nearest_catalyst: activeCatalystSchema.nullable(),
  catalyst_window_days: z.number(),

  // Per-action status
  covered_calls_status: actionStatusSchema,
  partial_sells_status: actionStatusSchema,
  trims_status: actionStatusSchema,

  // Active overrides
  covered_calls_override: overrideDetailSchema.nullable(),
  partial_sells_override: overrideDetailSchema.nullable(),
  trims_override: overrideDetailSchema.nullable(),

  // Exit rule conflict / deferral
  exit_rule_active: z.boolean().nullable(),
  exit_rule_deferred: z.boolean(),
  exit_rule_deferred_until: z.string().nullable(),
  exit_deferral_trading_days: z.number(),

  // Data source availability
  f7_available: z.boolean(),
  catalyst_db_available: z.boolean(),
  section16_available: z.boolean(),

  // Data quality
  data_gap_severity: z.string(),
  warning_messages: z.array(z.string()),
  last_updated: z.string(),
  cache_hit: z.boolean(),
});

export const framework12StatusResultSchema = z.object({
  no_fly_status: noFlyStatusSchema,
  no_fly_active: z.boolean().nullable(),
  covered_calls_status: actionStatusSchema,
  partial_sells_status: actionStatusSchema,
  trims_status: actionStatusSchema,
  nearest_catalyst_date: z.string().nullable(),
  nearest_catalyst_type: catalystTypeSchema.nullable(),
  days_to_catalyst: z.number().nullable(),
  exit_rule_deferred: z.boolean(),
  exit_rule_deferred_until: z.string().nullable(),
  data_gap_severity: z.string(),
});

export const framework12PortfolioSummarySchema = z.object({
  tickers_in_no_fly: z.array(z.string()),
  tickers_clear: z.array(z.string()),
  tickers_unknown: z.array(z.string()),
  total_held: z.number(),
  active_catalysts_count: z.number(),
});

// ---------------------------------------------------------------------------
// Write request / response schemas
// ---------------------------------------------------------------------------

export const addCatalystRequestSchema = z.object({
  ticker: z.string().min(1),
  catalyst_type: z.string(),
  catalyst_date: z.string(),
  description: z.string().optional(),
  entered_by: z.string().optional(),
});

export const catalystResponseSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  catalyst_type: z.string(),
  catalyst_date: z.string(),
  description: z.string().nullable(),
  status: z.string(),
  entered_by: z.string().nullable(),
});

export const addOverrideRequestSchema = z.object({
  action_type: z.string(),
  override_reason: z.string().min(1),
  override_duration_hours: z.number().int().positive(),
  entered_by: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Exported types
// ---------------------------------------------------------------------------

export type CatalystType = z.infer<typeof catalystTypeSchema>;
export type NoFlyStatus = z.infer<typeof noFlyStatusSchema>;
export type ActionStatus = z.infer<typeof actionStatusSchema>;
export type ActiveCatalyst = z.infer<typeof activeCatalystSchema>;
export type OverrideDetail = z.infer<typeof overrideDetailSchema>;
export type Framework12Result = z.infer<typeof framework12ResultSchema>;
export type Framework12StatusResult = z.infer<
  typeof framework12StatusResultSchema
>;
export type Framework12PortfolioSummary = z.infer<
  typeof framework12PortfolioSummarySchema
>;
export type AddCatalystRequest = z.infer<typeof addCatalystRequestSchema>;
export type CatalystResponse = z.infer<typeof catalystResponseSchema>;
export type AddOverrideRequest = z.infer<typeof addOverrideRequestSchema>;
