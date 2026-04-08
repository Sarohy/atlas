import { z } from 'zod';

export const cashUpdateSchema = z.object({
  cash_balance: z.coerce.number().gte(0),
  cash_floor_pct: z.coerce.number().gte(0).lte(1).default(0.1),
});

/** Schema for the additive-delta cash adjustment request. No min bound — negative = withdrawal. */
export const cashAdjustSchema = z.object({
  delta: z.coerce.number(),
});

export const cashResponseSchema = z.object({
  cash_balance: z.coerce.number(),
  cash_floor_pct: z.coerce.number(),
});

export const portfolioSummarySchema = z.object({
  total_nav: z.coerce.number(),
  invested_value: z.coerce.number(),
  invested_pct: z.coerce.number(),
  cash_balance: z.coerce.number(),
  cash_pct: z.coerce.number(),
  cash_floor: z.coerce.number(),
  /** Expressed as 0–100, not 0–1. */
  cash_floor_pct: z.coerce.number(),
  deployable: z.coerce.number(),
  day_change: z.coerce.number().nullable(),
  beta_total: z.coerce.number().nullable(),
  beta_invested: z.coerce.number().nullable(),
});

export type CashUpdate = z.infer<typeof cashUpdateSchema>;
export type CashAdjust = z.infer<typeof cashAdjustSchema>;
export type CashResponse = z.infer<typeof cashResponseSchema>;
export type PortfolioSummary = z.infer<typeof portfolioSummarySchema>;
