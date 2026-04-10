import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-indicator schemas
// F4 weights: Whale Block 35% | Call/Put Ratio 20% | Vol/OI 20% | Dark Pool 15% | Sweep 10%
// Each indicator score is 0-100; F4 = weighted sum.
// Collar flag caps F4 at 68.
// ---------------------------------------------------------------------------

export const whaleBlockIndicatorSchema = z.object({
  /** Largest single-print premium in USD. */
  largest_premium: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.35),
});

export const callPutRatioIndicatorSchema = z.object({
  call_premium: z.number().nullable(),
  put_premium: z.number().nullable(),
  /** call_premium / put_premium. Null when no data. */
  ratio: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.20),
});

export const volumeOiIndicatorSchema = z.object({
  call_volume: z.number().nullable(),
  call_open_interest: z.number().nullable(),
  /** call_volume / call_open_interest. */
  vol_oi_ratio: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.20),
});

export const darkPoolIndicatorSchema = z.object({
  total_dark_pool_premium: z.number().nullable(),
  largest_print: z.number().nullable(),
  print_count: z.number().int().min(0),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.15),
});

export const sweepTypeIndicatorSchema = z.object({
  has_golden_sweep: z.boolean(),
  has_single_sweep: z.boolean(),
  has_repeated_hits: z.boolean(),
  sweep_premium: z.number().nullable(),
  score: z.number().int().min(0).max(100),
  weight: z.number().default(0.10),
});

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const optionsFlowResponseSchema = z.object({
  ticker: z.string(),
  whale_block: whaleBlockIndicatorSchema,
  call_put_ratio: callPutRatioIndicatorSchema,
  volume_oi: volumeOiIndicatorSchema,
  dark_pool: darkPoolIndicatorSchema,
  sweep_type: sweepTypeIndicatorSchema,
  /** Highest signal tier: GOLD | BLUE | GREEN | YELLOW | GREY | WHITE | NONE */
  signal_tier: z.string(),
  /** True when a collar structure is detected — score capped at 68. */
  collar_flag: z.boolean(),
  f4_score: z.number().int().min(0).max(100),
  f4_grade: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type WhaleBlockIndicator = z.infer<typeof whaleBlockIndicatorSchema>;
export type CallPutRatioIndicator = z.infer<typeof callPutRatioIndicatorSchema>;
export type VolumeOiIndicator = z.infer<typeof volumeOiIndicatorSchema>;
export type DarkPoolIndicator = z.infer<typeof darkPoolIndicatorSchema>;
export type SweepTypeIndicator = z.infer<typeof sweepTypeIndicatorSchema>;
export type OptionsFlowResponse = z.infer<typeof optionsFlowResponseSchema>;
