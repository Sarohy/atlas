import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const convictionActionResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  /** Raw Framework Score before regime adjustment (0-100). */
  base_score: z.number().int().min(0).max(100),

  /** Framework Score after regime modifier applied (0-100). */
  adjusted_score: z.number().int().min(0).max(100),

  /** Active Framework 2 regime rule: CRISIS | CAUTION | CLEAR | NORMAL. */
  rule: z.string(),

  /** Internal tier identifier: HOLD | READY | EARLY | RADAR | EXIT. */
  tier_key: z.string(),

  /** Human-readable status label for the conviction tier. */
  status: z.string(),

  /** Ordered list of recommended action lines. */
  actions: z.array(z.string()),

  /** UI tone class: green | cyan | yellow | orange | red. */
  tone: z.string(),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type ConvictionActionResponse = z.infer<typeof convictionActionResponseSchema>;
