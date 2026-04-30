import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas — F3 v7.3.4 base-score + modifier approach
// Priority 1: Consensus label  → base score (SB 90 / Buy 78 / Hold 55 / Sell 30)
// Priority 2: Analyst count    → modifier (+8/+5/+3/0/-5)
// Priority 3: PT revision dir  → modifier (+5/+3/0/-5/-10)
// Priority 4: Net upgrades 30d → modifier (+5/+3/0/-5/-10)
// Priority 5: Price vs target  → adjustment (applied last)
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
  /** v7.3.4 base score for this consensus label (90/78/55/30). Null when no data. */
  base_score: z.number().int().nullable().optional(),
});

export const analystCoverageIndicatorSchema = z.object({
  num_analysts: z.number().int().min(0),
  /** v7.3.4 analyst count modifier (+8/+5/+3/0/-5). Null when no coverage data. */
  modifier: z.number().int().nullable().optional(),
});

export const ptDirectionIndicatorSchema = z.object({
  raises_30d: z.number().int().min(0),
  lowers_30d: z.number().int().min(0),
  /**
   * MULTIPLE_RAISES | SINGLE_RAISE | NO_CHANGE | SINGLE_CUT | MULTIPLE_CUTS | NO_DATA
   */
  direction_label: z.string(),
  /** v7.3.4 PT revision modifier (+5/+3/0/-5/-10). Null when Benzinga data unavailable. */
  modifier: z.number().int().nullable().optional(),
});

export const recentUpgradesIndicatorSchema = z.object({
  upgrades_30d: z.number().int().min(0),
  downgrades_30d: z.number().int().min(0),
  net_upgrades_30d: z.number().int(),
  /** v7.3.4 upgrade/downgrade modifier (+5/+3/0/-5/-10). Null when unavailable. */
  modifier: z.number().int().nullable().optional(),
});

export const ptUpsideIndicatorSchema = z.object({
  current_price: z.number().nullable(),
  consensus_pt: z.number().nullable(),
  /** Percentage upside from current price to consensus PT. Negative = stock above target. */
  upside_pct: z.number().nullable(),
  /** (current_price - consensus_pt) / consensus_pt, rounded to 4 dp. */
  price_vs_target: z.number().nullable().optional(),
  /** Band label: '20%+ below target (+10)' | '10-20% below target (+5)' | etc. */
  price_vs_target_band: z.string().nullable().optional(),
  /** Score adjustment applied by the price vs target band. */
  adjustment: z.number().int().nullable().optional(),
  /** Semantic colour token from the backend: GREEN | LIGHT_GREEN | NEUTRAL | AMBER | RED */
  upside_color: z.string().nullable().optional(),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const analystResponseSchema = z.object({
  ticker: z.string(),
  consensus_rating: consensusRatingIndicatorSchema,
  analyst_coverage: analystCoverageIndicatorSchema,
  pt_direction: ptDirectionIndicatorSchema,
  recent_upgrades: recentUpgradesIndicatorSchema,
  pt_upside: ptUpsideIndicatorSchema,
  /** base + count_mod + pt_mod + upgrade_mod before price adjustment. */
  f3_before_price_adjustment: z.number().int().nullable().optional(),
  /** True when the high consensus override lifted the score to 78 minimum. */
  override_applied: z.boolean().default(false),
  /** Reason string when override fired. */
  override_reason: z.string().nullable().optional(),
  f3_score: z.number().int().min(0).max(100).nullable(),
  f3_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type ConsensusRatingIndicator = z.infer<typeof consensusRatingIndicatorSchema>;
export type AnalystCoverageIndicator = z.infer<typeof analystCoverageIndicatorSchema>;
export type PtDirectionIndicator = z.infer<typeof ptDirectionIndicatorSchema>;
export type RecentUpgradesIndicator = z.infer<typeof recentUpgradesIndicatorSchema>;
export type PtUpsideIndicator = z.infer<typeof ptUpsideIndicatorSchema>;
export type AnalystResponse = z.infer<typeof analystResponseSchema>;
