import { z } from 'zod';

export const positionSizingResponseSchema = z.object({
  ticker: z.string(),
  conviction_score: z.number().int().min(0).max(100),
  action: z.string(),
  instruction: z.string(),
});

export type PositionSizingResponse = z.infer<typeof positionSizingResponseSchema>;
