import { z } from 'zod';

export const positionSizingResponseSchema = z.object({
  ticker: z.string(),
  conviction_score: z.number().int().min(0).max(100),
  tier: z.enum(['T1_ELITE', 'T1', 'T2', 'T3', 'BELOW_GATE']),
  action: z.string(),
  grey_zone: z.boolean(),
  consensus_required: z.boolean(),
  trigger_exit_rules: z.boolean(),
  adds_permitted: z.boolean(),
  leaps_eligible: z.boolean(),
  display_message: z.string(),
  consensus_confirmed: z.boolean(),
});

export type PositionSizingResponse = z.infer<typeof positionSizingResponseSchema>;

/** Convenience type for the position tier. */
export type PositionTier = z.infer<typeof positionSizingResponseSchema>['tier'];
