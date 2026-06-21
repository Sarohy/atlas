import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

/** Contribution of a single factor (F1–F5) to the Framework Score. */
export const factorBreakdownSchema = z.object({
  /** Factor identifier: 'f1' … 'f5' */
  key: z.string(),
  /** Human-readable factor name */
  name: z.string(),
  /** Composite factor score 0-100 */
  score: z.number().int().min(0).max(100),
  /** Framework weighting for this factor (e.g. 0.20 for F1) */
  weight: z.number(),
  /** Weighted contribution: score × weight */
  contribution: z.number(),
  /** Factor-level grade (e.g. 'STRONG BUY', 'NEUTRAL') */
  grade: z.string(),
  /** False when the factor could not be computed; neutral score 50 used */
  available: z.boolean().default(true),
  /** F4 only: Flow Monitor final action (the add gate). */
  flow_monitor_action: z.string().nullable().optional(),
});

export const etfBranchComponentSchema = z.object({
  name: z.string(),
  weight: z.number().gt(0).lte(1),
  score: z.number().int().min(0).max(100),
});

export const etfHedgeInputsSchema = z.object({
  purpose: z.string(),
  underlying: z.string(),
  portfolio_beta_covered: z.array(z.string()).default([]),
  iv_rank: z.number().min(0).max(100).nullable().default(null),
  delta: z.number().min(-1).max(1).nullable().default(null),
  expiry_days: z.number().int().min(0).nullable().default(null),
  max_hold_days: z.number().int().min(0).nullable().default(null),
});

export const etfConstituentSchema = z.object({
  symbol: z.string(),
  weight_pct: z.number().min(0).max(100),
  scored: z.boolean(),
  note: z.string().nullable().default(null),
});

export const intlFactorSchema = z.object({
  key: z.string(),
  name: z.string(),
  score: z.number().int().min(0).max(100),
  available: z.boolean(),
  source: z.string(),
});

export const intlDataTaskSchema = z.object({
  item: z.string(),
  status: z.string(),
});

export const intlBranchMetadataSchema = z.object({
  route: z.string(),
  label: z.string(),
  headline_label: z.string(),
  instrument_kind: z.string(),
  coverage_label: z.string(),
  domestic_note: z.string().default('Domestic F1–F5 not applicable.'),
  f4_note: z.string().default('F4 N/A — no U.S. flow coverage (unavailable, not bearish).'),
  rank_pending: z.boolean().default(false),
  size_capped: z.boolean().default(false),
  factors: z.array(intlFactorSchema).default([]),
  labels: z.array(z.string()).default([]),
  data_tasks: z.array(intlDataTaskSchema).default([]),
});

export const etfBranchMetadataSchema = z.object({
  route: z.string(),
  label: z.string(),
  headline_label: z.string(),
  timing_overlay_role: z.string(),
  holdings_driver: z.string().nullable().default(null),
  components: z.array(etfBranchComponentSchema).default([]),
  constituents: z.array(etfConstituentSchema).default([]),
  scored_coverage_pct: z.number().min(0).max(100).nullable().default(null),
  coverage_note: z.string().nullable().default(null),
  hedge_inputs: etfHedgeInputsSchema.nullable().default(null),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const frameworkScoreResponseSchema = z.object({
  /** Ticker symbol (upper-case) */
  ticker: z.string(),
  /** Ordered list of factor breakdowns: F1, F2, F3, F4, F5 */
  factors: z.array(factorBreakdownSchema),
  /** Weighted sum of all factor contributions (max 95) */
  raw_total: z.number().min(0).max(95),
  /** Final ATLAS conviction score: round(raw_total), [0, 100] */
  final_score: z.number().int().min(0).max(100),
  /**
   * Recommended action per Factor_Mapping_Guide score–action map:
   * 'MAXIMUM POSITION' | 'HOLD / ADD' | 'HOLD' | 'REDUCE' | 'REDUCE FURTHER' | 'EXIT'
   */
  action: z.string(),
  /**
   * CSS tone class for colour-coding the action badge:
   * 'tone-green' | 'tone-cyan' | 'tone-yellow' | 'tone-orange' | 'tone-red' | 'tone-dark-red'
   */
  action_tone: z.string(),
  /** True when F5 Altman Z < 1.8 — hard block on new capital */
  f5_blocked: z.boolean().default(false),
  /** Human-readable flag messages */
  flags: z.array(z.string()).default([]),
  /** True when F2 or F5 used AV rate-limit fallback scores — do not cache */
  degraded: z.boolean().default(false),
  /** Badge label when Framework 9 F4 data is incomplete */
  f4_data_gap_badge: z.string().nullable().default(null),
  /** Human-readable message for the F4 data gap */
  f4_data_gap_message: z.string().nullable().default(null),
  /** Tooltip text for the F4 data gap badge */
  f4_data_gap_tooltip: z.string().nullable().default(null),

  // --- Framework 8 insider buying bonus ---
  /** Raw F5 score before any adjustments. Null when F5 unavailable. */
  f5_raw_score: z.number().int().min(0).max(100).nullable().default(null),
  /** Additive bonus applied to the framework score from insider buying activity. */
  f8_buying_bonus: z.number().int().min(0).default(0),
  /**
   * Display-only note when multiple C-suite insiders sell without a 10b5-1 plan.
   * Null when no concern. Carries no scoring impact.
   */
  f8_clustered_selling_note: z.string().nullable().default(null),
  /** Optional expanded F5 debug bridge propagated from backend. */
  f5_debug_bridge: z
    .object({
      altman_z_score: z.number().nullable().optional(),
      altman_variant_used: z.string().optional(),
      x1_working_capital_to_assets: z.number().nullable().optional(),
      x2_retained_earnings_to_assets: z.number().nullable().optional(),
      x3_ebit_to_assets: z.number().nullable().optional(),
      x4_market_equity_to_liabilities: z.number().nullable().optional(),
      x5_sales_to_assets: z.number().nullable().optional(),
      current_assets_usd: z.number().nullable().optional(),
      current_liabilities_usd: z.number().nullable().optional(),
      deferred_revenue_current_usd: z.number().nullable().optional(),
      working_capital_usd: z.number().nullable().optional(),
      cash_claim_working_capital_usd: z.number().nullable().optional(),
      cash_usd: z.number().nullable().optional(),
      short_term_debt_usd: z.number().nullable().optional(),
      total_debt_usd: z.number().nullable().optional(),
      net_debt_usd: z.number().nullable().optional(),
      ebit_interest_coverage: z.number().nullable().optional(),
      interest_expense_ttm_usd: z.number().nullable().optional(),
      qoq_working_capital_change_usd: z.number().nullable().optional(),
      qoq_working_capital_trend: z.string().nullable().optional(),
      qoq_debt_change_usd: z.number().nullable().optional(),
      qoq_debt_trend: z.string().nullable().optional(),
      piotroski_score: z.number().int().nullable().optional(),
      piotroski_is_supporting_vendor_signal: z.boolean().optional(),
    })
    .nullable()
    .optional(),
  /** ETF branch metadata from universal router + branch model. */
  etf_branch: etfBranchMetadataSchema.nullable().default(null),
  /** INTL-3F branch metadata for foreign/ADR/OTC operating companies. */
  intl_branch: intlBranchMetadataSchema.nullable().default(null),
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type FactorBreakdown = z.infer<typeof factorBreakdownSchema>;
export type EtfBranchComponent = z.infer<typeof etfBranchComponentSchema>;
export type EtfConstituent = z.infer<typeof etfConstituentSchema>;
export type EtfHedgeInputs = z.infer<typeof etfHedgeInputsSchema>;
export type EtfBranchMetadata = z.infer<typeof etfBranchMetadataSchema>;
export type IntlFactor = z.infer<typeof intlFactorSchema>;
export type IntlDataTask = z.infer<typeof intlDataTaskSchema>;
export type IntlBranchMetadata = z.infer<typeof intlBranchMetadataSchema>;
export type FrameworkScoreResponse = z.infer<typeof frameworkScoreResponseSchema>;
