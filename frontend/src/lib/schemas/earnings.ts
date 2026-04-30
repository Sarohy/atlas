import { z } from 'zod';

// ---------------------------------------------------------------------------
// Flat top-level response schema — v7.3.4
// Mirrors backend schemas/earnings.py EarningsResponse
// ---------------------------------------------------------------------------

export const earningsResponseSchema = z.object({
  ticker: z.string(),

  // Sub-factor 1 — Revenue Growth YoY (weight 30%)
  sf1_revenue_growth_pct: z.number().nullable(),
  sf1_score: z.number().min(0).max(100),

  // Sub-factor 2 — Gross Margin Trend (weight 20%)
  sf2_gross_margin_trend_bps: z.number().nullable(),
  sf2_score: z.number().min(0).max(100),

  // Sub-factor 3 — EPS Beat Consistency 4Q (weight 20%; excluded when pre-profit)
  sf3_eps_beats: z.number().int().nullable(),
  sf3_quarters_available: z.number().int().min(0),
  sf3_score: z.number().min(0).max(100).nullable(),
  sf3_excluded: z.boolean(),

  // Sub-factor 4 — Guidance Reliability 4Q (weight 15%)
  sf4_guidance_delivered: z.number().int().nullable(),
  sf4_score: z.number().min(0).max(100),
  sf4_data_gap: z.boolean(),

  // Sub-factor 5 — Forward Visibility (weight 15%)
  sf5_forward_visibility_label: z.string(),
  sf5_score: z.number().min(0).max(100),

  // F2 composite
  f2_raw: z.number().min(0).max(100),
  f2_contribution: z.number(),
  f2_score: z.number().int().min(0).max(100),
  f2_grade: z.string(),

  // Flags
  pre_profit_status: z.boolean().default(false),
  pre_profit_reweighted: z.boolean().default(false),
  data_gap_applied: z.boolean().default(false),
  guidance_concern: z.boolean().default(false),
  exit_flag: z.boolean().default(false),
  limited_history: z.boolean().default(false),
  ipo_limited_history: z.boolean().default(false),
  data_available: z.boolean().default(true),
  is_pre_profitability: z.boolean().default(false),

  breakdown: z.record(z.string(), z.unknown()).default({}),
});

// ---------------------------------------------------------------------------
// TypeScript type
// ---------------------------------------------------------------------------

export type EarningsResponse = z.infer<typeof earningsResponseSchema>;
