import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const cashFloorResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  /** Framework 2 rule that fired: 1=CRISIS HALT, 2=CAUTION, 3=SOFT CAUTION, 4=CLEAR. null = no rule. */
  rule_triggered: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).nullable(),

  /** Brent crude price in USD per barrel at evaluation time. */
  brent_price: z.number().nullable(),

  /** CBOE VIX index level at evaluation time. */
  vix_value: z.number().nullable(),

  /** Regime condition: CRISIS | CAUTION | CLEAR | FULLY_DEPLOYED */
  condition: z.string(),

  /** Human-readable rationale for the floor requirement. */
  rationale: z.string(),

  /** Minimum cash floor as a fraction of position value (e.g. 0.35 = 35%). */
  floor_pct_min: z.number(),

  /** Maximum cash floor as a fraction of position value. */
  floor_pct_max: z.number(),

  /** Current portfolio position value in USD — null when ticker not in portfolio. */
  position_value_usd: z.number().nullable(),

  /** Minimum cash to hold in USD — null when ticker not in portfolio. */
  floor_usd_min: z.number().nullable(),

  /** Maximum cash to hold in USD — null when ticker not in portfolio. */
  floor_usd_max: z.number().nullable(),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type CashFloorResponse = z.infer<typeof cashFloorResponseSchema>;
