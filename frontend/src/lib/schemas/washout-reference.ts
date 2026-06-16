import { z } from 'zod';

/** Response from GET /api/v1/extension-washout/reference — Settings + Risk views. */
export const washoutReferenceResponseSchema = z.object({
  thresholds: z
    .array(z.object({ key: z.string(), value: z.string(), group: z.string() }))
    .default([]),
  exceptions: z
    .array(
      z.object({
        ticker: z.string(),
        track: z.string(),
        overshoot: z.string(),
        elasticity_tier: z.string(),
        flags: z.array(z.string()).default([]),
        note: z.string().default(''),
      }),
    )
    .default([]),
});

export type WashoutReferenceResponse = z.infer<typeof washoutReferenceResponseSchema>;
