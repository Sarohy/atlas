import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// F5 weights: Insider 30% | Altman Z 25% | FCF 20% | Debt/Equity 15% | Institutional 10%
// Each indicator score is 0-100; F5 = weighted sum, then caps applied.
// ---------------------------------------------------------------------------

export const insiderActivityIndicatorSchema = z.object({
  /** Total USD value of insider purchases last 90 days. */
  net_buy_value: z.number().nullable(),
  /** Total USD value of insider sales last 90 days. */
  net_sell_value: z.number().nullable(),
  transaction_count: z.number().int().min(0),
  /** Total C-suite officer disposal value (USD). */
  c_suite_sell_value: z.number().nullable(),
  /** CEO or CFO disposal value — triggers mega-sale cap above $10M. */
  ceo_cfo_sell_value: z.number().nullable(),
  /** NET_BUYING | NO_ACTIVITY | SMALL_SALE | MULTIPLE_SALES | CEO_MEGA_SALE */
  activity_label: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.30),
});

export const altmanZScoreIndicatorSchema = z.object({
  /** Computed Altman Z-Score. Null when data insufficient. */
  z_score: z.number().nullable(),
  x1_working_capital_ratio: z.number().nullable(),
  x2_retained_earnings_ratio: z.number().nullable(),
  x3_ebit_ratio: z.number().nullable(),
  x4_market_cap_to_liabilities: z.number().nullable(),
  x5_revenue_to_assets: z.number().nullable(),
  /** SAFE | GREY | DISTRESSED | UNKNOWN */
  zone: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.25),
});

export const freeCashFlowIndicatorSchema = z.object({
  /** Most recent quarter FCF in USD. */
  fcf_current: z.number().nullable(),
  /** Prior quarter FCF in USD (trend baseline). */
  fcf_prior: z.number().nullable(),
  /**
   * POSITIVE_GROWING | POSITIVE_FLAT | POSITIVE_DECLINING
   * | NEGATIVE_IMPROVING | NEGATIVE_WORSENING | UNKNOWN
   */
  fcf_trend: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.20),
});

export const debtEquityIndicatorSchema = z.object({
  /** Total debt (short + long term) in USD. */
  total_debt: z.number().nullable(),
  /** Total shareholder equity in USD. */
  total_equity: z.number().nullable(),
  /** Debt / Equity ratio. Null when equity is zero or data missing. */
  ratio: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.15),
});

export const institutionalOwnershipIndicatorSchema = z.object({
  /** Current institutional ownership as a fraction (0.0–1.0). */
  ownership_pct: z.number().nullable(),
  /** NET_BUYING | FLAT | SMALL_SELLING | LARGE_SELLING */
  change_label: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.10),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const fundamentalResponseSchema = z.object({
  ticker: z.string(),
  insider_activity: insiderActivityIndicatorSchema,
  altman_z: altmanZScoreIndicatorSchema,
  free_cash_flow: freeCashFlowIndicatorSchema,
  debt_equity: debtEquityIndicatorSchema,
  institutional_ownership: institutionalOwnershipIndicatorSchema,

  /** F5 cap from insider selling: 72 (officer >$1M) or 65 (CEO/CFO >$10M). Null = no cap. */
  insider_cap: z.number().int().nullable(),
  /** F5 cap from Altman Z grey zone: 75. Null = not in grey zone. */
  altman_cap: z.number().int().nullable(),
  /** True when Altman Z < 1.8 — new capital hard-blocked. */
  f5_blocked: z.boolean(),
  /** Lowest of insider_cap and altman_cap, or null if no caps active. */
  active_cap: z.number().int().nullable(),

  f5_score: z.number().int().min(0).max(100),
  /** STRONG | GOOD | NEUTRAL | WEAK | DISTRESSED */
  f5_grade: z.string(),
  /** False when Alpha Vantage was rate-limited — scores are fallback values. */
  data_available: z.boolean().default(true),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type InsiderActivityIndicator = z.infer<typeof insiderActivityIndicatorSchema>;
export type AltmanZScoreIndicator = z.infer<typeof altmanZScoreIndicatorSchema>;
export type FreeCashFlowIndicator = z.infer<typeof freeCashFlowIndicatorSchema>;
export type DebtEquityIndicator = z.infer<typeof debtEquityIndicatorSchema>;
export type InstitutionalOwnershipIndicator = z.infer<typeof institutionalOwnershipIndicatorSchema>;
export type FundamentalResponse = z.infer<typeof fundamentalResponseSchema>;
