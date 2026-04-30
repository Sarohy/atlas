import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const ladderTierResultSchema = z.object({
  tier_order: z.number(),
  duration_min_days: z.number(),
  duration_max_days: z.number().nullable(),
  brent_range_low: z.number(),
  brent_range_high: z.number().nullable(),
  fed_implication: z.string(),
  portfolio_action: z.string(),
});

export const framework28ResultSchema = z.object({
  f17_active: z.boolean().nullable(),
  conflict_duration_days: z.number().nullable(),
  brent_price: z.number().nullable(),
  active_tier: ladderTierResultSchema.nullable().default(null),
  all_tiers: z.array(ladderTierResultSchema).default([]),
  ladder_active: z.boolean().default(false),
  no_match_reason: z.string().nullable().default(null),
  cache_hit: z.boolean().default(false),
  data_as_of: z.string().nullable().default(null),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type LadderTierResult = z.infer<typeof ladderTierResultSchema>;
export type Framework28Result = z.infer<typeof framework28ResultSchema>;
