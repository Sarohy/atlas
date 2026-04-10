import { z } from 'zod';

export const marketConditionsSchema = z.object({
  /** Most recent Brent crude daily close (USD per barrel), or null */
  brent_price: z.number().nullable(),

  /** Previous Brent crude daily close — used for two-consecutive-closes Rule 3 check */
  brent_prev_price: z.number().nullable(),

  /** Latest CBOE VIX index level, or null */
  vix_value: z.number().nullable(),
});

export type MarketConditions = z.infer<typeof marketConditionsSchema>;
