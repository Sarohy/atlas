import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const insiderTierSchema = z.enum(['TIER1', 'TIER2', 'TIER3']);

export const framework8ResponseSchema = z.object({
  /** Ticker symbol. */
  ticker: z.string(),

  /** True when discretionary insider selling has been detected. */
  flag_active: z.boolean(),

  /**
   * True when the pattern is disqualifying — many sales, zero purchases.
   * The ticker should be removed from the investable universe.
   */
  hard_pass: z.boolean(),

  /**
   * Seniority tier of the filer who triggered the flag.
   * Null when flag_active is false.
   */
  filer_tier: insiderTierSchema.nullable(),

  /** USD value of the largest discretionary sale detected. Null when no flag. */
  largest_sale_usd: z.number().nullable(),

  /**
   * Cap to apply to Framework 5 score.
   * 68 = large sale (≥ $1M) or Tier 1 filer.
   * 72 = standard discretionary sale.
   * Null when flag is inactive.
   */
  f5_cap: z.number().int().nullable(),

  /** Data source: "hardcoded" | "sec_edgar" | "default". */
  source: z.enum(['hardcoded', 'sec_edgar', 'default']),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type InsiderTier = z.infer<typeof insiderTierSchema>;
export type Framework8Response = z.infer<typeof framework8ResponseSchema>;
