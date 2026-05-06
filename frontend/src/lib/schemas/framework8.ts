import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const framework8ResponseSchema = z.object({
  /** Ticker symbol. */
  ticker: z.string(),

  /** Additive score bonus from insider buying activity (0 when no qualifying buys). */
  buying_bonus: z.number().int().min(0).default(0),

  /**
   * Display-only note when multiple Tier-1 insiders sell without a 10b5-1 plan.
   * Null when no concern detected. Carries NO scoring impact.
   */
  clustered_selling_note: z.string().nullable().default(null),

  /** Data source: "sec_edgar" | "default". */
  source: z.enum(['sec_edgar', 'default']),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type Framework8Response = z.infer<typeof framework8ResponseSchema>;
