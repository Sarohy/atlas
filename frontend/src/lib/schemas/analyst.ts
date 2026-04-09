import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// ---------------------------------------------------------------------------

export const consensusRatingIndicatorSchema = z.object({
  buy_count: z.number().int().min(0),
  hold_count: z.number().int().min(0),
  sell_count: z.number().int().min(0),
  total_analysts: z.number().int().min(0),
  /** Buy ratings as a percentage of total (0-100). Null when no analysts. */
  buy_pct: z.number().nullable(),
  /** STRONG BUY | BUY | HOLD | UNDERPERFORM | SELL | NO DATA */
  label: z.string(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const ptUpsideIndicatorSchema = z.object({
  current_price: z.number().nullable(),
  consensus_pt: z.number().nullable(),
  /** Percentage upside from current price to consensus PT. Negative = downside. */
  upside_pct: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const ptDirectionIndicatorSchema = z.object({
  current_consensus_pt: z.number().nullable(),
  prior_consensus_pt: z.number().nullable(),
  /** Percentage change in consensus PT (positive = being raised). */
  direction_pct: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const analystCoverageIndicatorSchema = z.object({
  num_analysts: z.number().int().min(0),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const recentUpgradesIndicatorSchema = z.object({
  upgrades: z.number().int().min(0),
  downgrades: z.number().int().min(0),
  /** upgrades - downgrades. Positive = net bullish analyst action. */
  net_upgrades: z.number().int(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const analystResponseSchema = z.object({
  ticker: z.string(),
  consensus_rating: consensusRatingIndicatorSchema,
  pt_upside: ptUpsideIndicatorSchema,
  pt_direction: ptDirectionIndicatorSchema,
  analyst_coverage: analystCoverageIndicatorSchema,
  recent_upgrades: recentUpgradesIndicatorSchema,
  f3_score: z.number().int().min(0).max(100),
  f3_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type ConsensusRatingIndicator = z.infer<typeof consensusRatingIndicatorSchema>;
export type PtUpsideIndicator = z.infer<typeof ptUpsideIndicatorSchema>;
export type PtDirectionIndicator = z.infer<typeof ptDirectionIndicatorSchema>;
export type AnalystCoverageIndicator = z.infer<typeof analystCoverageIndicatorSchema>;
export type RecentUpgradesIndicator = z.infer<typeof recentUpgradesIndicatorSchema>;
export type AnalystResponse = z.infer<typeof analystResponseSchema>;
