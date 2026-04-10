import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// F3 weights: Consensus 35% | Coverage 10% | PT Upside 30% | PT Revision 25%
// Each indicator score is 0-100; F3 = weighted sum.
// ---------------------------------------------------------------------------

export const consensusRatingIndicatorSchema = z.object({
  strong_buy_count: z.number().int().min(0),
  buy_count: z.number().int().min(0),
  hold_count: z.number().int().min(0),
  sell_count: z.number().int().min(0),
  strong_sell_count: z.number().int().min(0),
  total_analysts: z.number().int().min(0),
  /** (Strong Buy + Buy) as a percentage of total (0-100). Null when no analysts. */
  buy_pct: z.number().nullable(),
  /** STRONG BUY | BUY | HOLD | SELL | NO DATA */
  label: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.35),
});

export const analystCoverageIndicatorSchema = z.object({
  num_analysts: z.number().int().min(0),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.10),
});

export const ptUpsideIndicatorSchema = z.object({
  current_price: z.number().nullable(),
  consensus_pt: z.number().nullable(),
  /** Percentage upside from current price to consensus PT. Negative = downside. */
  upside_pct: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.30),
});

export const ptRevisionIndicatorSchema = z.object({
  raises_30d: z.number().int().min(0),
  lowers_30d: z.number().int().min(0),
  /** MULTIPLE RAISES | 1 RAISE | NO CHANGE | LOWERED */
  revision_label: z.string(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.25),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const analystResponseSchema = z.object({
  ticker: z.string(),
  consensus_rating: consensusRatingIndicatorSchema,
  analyst_coverage: analystCoverageIndicatorSchema,
  pt_upside: ptUpsideIndicatorSchema,
  pt_revision: ptRevisionIndicatorSchema,
  f3_score: z.number().int().min(0).max(100),
  f3_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type ConsensusRatingIndicator = z.infer<typeof consensusRatingIndicatorSchema>;
export type AnalystCoverageIndicator = z.infer<typeof analystCoverageIndicatorSchema>;
export type PtUpsideIndicator = z.infer<typeof ptUpsideIndicatorSchema>;
export type PtRevisionIndicator = z.infer<typeof ptRevisionIndicatorSchema>;
export type AnalystResponse = z.infer<typeof analystResponseSchema>;
