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

  // --- Framework 8 insider cap sync fields ---
  /** Raw F5 score before any Framework 8 insider cap. Null when F5 unavailable. */
  f5_raw_score: z.number().int().min(0).max(100).nullable().default(null),
  /** True when Framework 8 insider flag is active and the cap was applied to F5. */
  f5_capped: z.boolean().default(false),
  /** The Framework 8 cap value applied to F5. Null when no cap active. */
  f5_cap_applied: z.number().int().nullable().default(null),
  /** Human-readable reason for the F5 cap. */
  f5_cap_source: z.string().nullable().default(null),
  /** True when Framework 8 was successfully fetched this evaluation. */
  f8_available: z.boolean().default(false),
  /** Framework 8 insider flag status. Null when F8 was unavailable. */
  f8_flag_active: z.boolean().nullable().default(null),
  /** True when Framework 8 data exceeded the staleness threshold. */
  f8_stale: z.boolean().default(false),
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type FactorBreakdown = z.infer<typeof factorBreakdownSchema>;
export type FrameworkScoreResponse = z.infer<typeof frameworkScoreResponseSchema>;
