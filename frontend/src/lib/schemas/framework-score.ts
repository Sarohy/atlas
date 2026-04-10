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
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type FactorBreakdown = z.infer<typeof factorBreakdownSchema>;
export type FrameworkScoreResponse = z.infer<typeof frameworkScoreResponseSchema>;
