import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const dataSourceStatusSchema = z.enum([
  'ONLINE',
  'PARTIAL',
  'STALE',
  'RATE_LIMITED',
  'OFFLINE',
]);

export const signalTierSchema = z.enum([
  'TIER_1_WHALE',
  'TIER_2_INSTITUTIONAL',
  'TIER_3_UNUSUAL',
  'TIER_4_WEAK',
  'TIER_5_NONE',
]);

export const flowDirectionSchema = z.enum(['BULLISH', 'BEARISH', 'NEUTRAL', 'MIXED']);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const dataGapDetailSchema = z.object({
  field: z.string(),
  source: z.string(),
  reason: z.string(),
  impact: z.string(),
  default_used: z.string(),
});

// ---------------------------------------------------------------------------
// Main result schema
// ---------------------------------------------------------------------------

export const framework9ResultSchema = z.object({
  ticker: z.string(),

  // F4 scoring outputs
  f4_score: z.number(),
  f4_grade: z.string(),
  f4_contribution: z.number(),

  // Signal classification
  signal_tier: signalTierSchema,
  flow_direction: flowDirectionSchema,

  // Raw data fields
  largest_print_usd: z.number().nullable(),
  dark_pool_spread_position: z.number().nullable(),
  dark_pool_direction: z.string().nullable(),
  put_call_ratio: z.number().nullable(),

  // Modifiers
  put_call_modifier: z.number().int(),
  dark_pool_modifier: z.number().int(),
  pre_earnings_modifier: z.number().int(),
  index_modifier: z.number().int(),

  // Volume / liquidity
  options_volume_vs_adv: z.number().nullable(),

  // Signal validity flags
  signal_valid: z.boolean(),
  minimum_threshold_met: z.boolean(),
  covered_call_exception: z.boolean(),
  covered_call_unverifiable: z.boolean(),
  pre_earnings_reduction: z.boolean(),
  conflicting_signals: z.boolean(),
  low_liquidity: z.boolean(),
  potential_index_flow: z.boolean(),

  // Source statuses
  uw_status: dataSourceStatusSchema,
  polygon_status: dataSourceStatusSchema,
  av_status: dataSourceStatusSchema,

  // Data gaps
  data_gaps: z.array(dataGapDetailSchema),
  data_gap_severity: z.string(),

  // F1 propagation
  f1_propagation_badge: z.string().nullable(),
  f1_propagation_message: z.string().nullable(),
  f1_propagation_tooltip: z.string().nullable(),

  // Warnings
  modifiers_skipped: z.array(z.string()),
  warning_level: z.enum(['NONE', 'AMBER', 'RED']),
  warning_messages: z.array(z.string()),

  // Raw breakdown
  breakdown: z.record(z.string(), z.unknown()),
});

// ---------------------------------------------------------------------------
// Inferred types
// ---------------------------------------------------------------------------

export type DataSourceStatus = z.infer<typeof dataSourceStatusSchema>;
export type SignalTier = z.infer<typeof signalTierSchema>;
export type FlowDirection = z.infer<typeof flowDirectionSchema>;
export type DataGapDetail = z.infer<typeof dataGapDetailSchema>;
export type Framework9Result = z.infer<typeof framework9ResultSchema>;
