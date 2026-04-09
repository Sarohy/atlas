import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// ---------------------------------------------------------------------------

export const revenueGrowthIndicatorSchema = z.object({
  current_ttm: z.number().nullable(),
  prior_ttm: z.number().nullable(),
  /** YoY TTM revenue growth (%). Null when prior TTM unavailable. */
  growth_pct: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const epsBeatsIndicatorSchema = z.object({
  /** Percentage of last 4 quarters where EPS beat consensus (0-100). */
  beat_rate_pct: z.number().nullable(),
  quarters_beat: z.number().int().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const guidanceIndicatorSchema = z.object({
  /** Net revision direction: +2 strongly raised … -2 strongly cut. */
  revision_direction: z.number().int().min(-2).max(2),
  revision_pct: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const backlogBtbIndicatorSchema = z.object({
  /** Book-to-bill proxy: positive = orders accelerating vs revenue. */
  btb_proxy: z.number().nullable(),
  revenue_acceleration: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const marginTrajectoryIndicatorSchema = z.object({
  /** Gross margin (%) for each of the last 4 quarters (oldest first). */
  gross_margins: z.array(z.number()),
  /** Average QoQ change in gross margin (ppts). Positive = expanding. */
  trajectory: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const earningsResponseSchema = z.object({
  ticker: z.string(),
  revenue_growth: revenueGrowthIndicatorSchema,
  eps_beats: epsBeatsIndicatorSchema,
  guidance: guidanceIndicatorSchema,
  backlog_btb: backlogBtbIndicatorSchema,
  margin_trajectory: marginTrajectoryIndicatorSchema,
  f2_score: z.number().int().min(0).max(100),
  f2_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type RevenueGrowthIndicator = z.infer<typeof revenueGrowthIndicatorSchema>;
export type EpsBeatsIndicator = z.infer<typeof epsBeatsIndicatorSchema>;
export type GuidanceIndicator = z.infer<typeof guidanceIndicatorSchema>;
export type BacklogBtbIndicator = z.infer<typeof backlogBtbIndicatorSchema>;
export type MarginTrajectoryIndicator = z.infer<typeof marginTrajectoryIndicatorSchema>;
export type EarningsResponse = z.infer<typeof earningsResponseSchema>;
