import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// ---------------------------------------------------------------------------

export const rsiIndicatorSchema = z.object({
  value: z.number().nullable(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const macdIndicatorSchema = z.object({
  macd_line: z.number(),
  signal_line: z.number(),
  histogram: z.number(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const maAlignmentIndicatorSchema = z.object({
  ma_20: z.number(),
  ma_50: z.number(),
  ma_200: z.number(),
  /** FULL_BULL | BULL | MIXED | BEAR | FULL_BEAR | INSUFFICIENT_DATA */
  label: z.string(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const week52PositionIndicatorSchema = z.object({
  high_52w: z.number(),
  low_52w: z.number(),
  /** 0 = at 52w low, 100 = at 52w high */
  position_pct: z.number().min(0).max(100),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const performanceIndicatorSchema = z.object({
  perf_1m: z.number(),
  perf_6m: z.number(),
  score_1m: z.number().int().min(0).max(10),
  score_6m: z.number().int().min(0).max(10),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

export const sectorMomentumIndicatorSchema = z.object({
  sector_etf: z.string(),
  ticker_perf_3m: z.number(),
  sector_perf_3m: z.number(),
  relative_perf_3m: z.number(),
  score: z.number().int().min(0).max(20),
  max_score: z.number().int().default(20),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const momentumResponseSchema = z.object({
  ticker: z.string(),
  sector_etf: z.string(),
  rsi: rsiIndicatorSchema,
  macd: macdIndicatorSchema,
  ma_alignment: maAlignmentIndicatorSchema,
  week_52_position: week52PositionIndicatorSchema,
  performance: performanceIndicatorSchema,
  sector_momentum: sectorMomentumIndicatorSchema,
  /** 0–100 composite F1 score */
  f1_score: z.number().int().min(0).max(100),
  /** STRONG BUY | BUY | NEUTRAL | WEAK | AVOID */
  f1_grade: z.string(),
});

// ---------------------------------------------------------------------------
// Exported TypeScript types
// ---------------------------------------------------------------------------

export type RsiIndicator = z.infer<typeof rsiIndicatorSchema>;
export type MacdIndicator = z.infer<typeof macdIndicatorSchema>;
export type MaAlignmentIndicator = z.infer<typeof maAlignmentIndicatorSchema>;
export type Week52PositionIndicator = z.infer<typeof week52PositionIndicatorSchema>;
export type PerformanceIndicator = z.infer<typeof performanceIndicatorSchema>;
export type SectorMomentumIndicator = z.infer<typeof sectorMomentumIndicatorSchema>;
export type MomentumResponse = z.infer<typeof momentumResponseSchema>;
