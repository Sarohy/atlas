import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas — mirrors backend schemas/earnings.py
// ---------------------------------------------------------------------------

export const revenueGrowthIndicatorSchema = z.object({
  /** YoY quarterly revenue growth (%). Null when data is unavailable. */
  yoy_pct: z.number().nullable(),
  /** Raw 0-100 score before weighting. */
  raw_score: z.number().int().min(0).max(100),
  /** Weighted F2 contribution (0-30). Weight: 30%. */
  score: z.number().int().min(0).max(30),
  max_score: z.number().int().default(30),
});

export const epsBeatsIndicatorSchema = z.object({
  /** Number of last 3 quarters where reportedEPS beat estimatedEPS (0-3). */
  beats_in_3: z.number().int().nullable(),
  /** How many of the last 3 quarters had sufficient EPS data. */
  quarters_checked: z.number().int().nullable(),
  /** Raw 0-100 score before weighting. */
  raw_score: z.number().int().min(0).max(100),
  /** Weighted F2 contribution (0-20). Weight: 20%. */
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const guidanceIndicatorSchema = z.object({
  /** Guidance classification from transcript NLP. */
  guidance_label: z.string(),
  /** Fiscal quarter of the transcript used (e.g. '2024Q3'). */
  transcript_quarter: z.string().nullable(),
  /** Raw 0-100 score before weighting. */
  raw_score: z.number().int().min(0).max(100),
  /** Weighted F2 contribution (0-20). Weight: 20%. */
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const marginTrajectoryIndicatorSchema = z.object({
  /** Gross-margin (%) values for last 3 quarters (oldest first). */
  gross_margins: z.array(z.number()),
  /** Gross-margin change in ppts (most recent minus oldest). Positive = expanding. */
  margin_change_pts: z.number().nullable(),
  /** Raw 0-100 score before weighting. */
  raw_score: z.number().int().min(0).max(100),
  /** Weighted F2 contribution (0-15). Weight: 15%. */
  score: z.number().int().min(0).max(15),
  max_score: z.number().int().default(15),
});

export const backlogBtbIndicatorSchema = z.object({
  /** Backlog classification from transcript NLP. */
  backlog_label: z.string(),
  /** Raw 0-100 score before weighting. */
  raw_score: z.number().int().min(0).max(100),
  /** Weighted F2 contribution (0-15). Weight: 15%. */
  score: z.number().int().min(0).max(15),
  max_score: z.number().int().default(15),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const earningsResponseSchema = z.object({
  ticker: z.string(),
  revenue_growth: revenueGrowthIndicatorSchema,
  eps_beats: epsBeatsIndicatorSchema,
  guidance: guidanceIndicatorSchema,
  margin_trajectory: marginTrajectoryIndicatorSchema,
  backlog_btb: backlogBtbIndicatorSchema,
  f2_score: z.number().int().min(0).max(100),
  f2_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type RevenueGrowthIndicator = z.infer<typeof revenueGrowthIndicatorSchema>;
export type EpsBeatsIndicator = z.infer<typeof epsBeatsIndicatorSchema>;
export type GuidanceIndicator = z.infer<typeof guidanceIndicatorSchema>;
export type MarginTrajectoryIndicator = z.infer<typeof marginTrajectoryIndicatorSchema>;
export type BacklogBtbIndicator = z.infer<typeof backlogBtbIndicatorSchema>;
export type EarningsResponse = z.infer<typeof earningsResponseSchema>;
