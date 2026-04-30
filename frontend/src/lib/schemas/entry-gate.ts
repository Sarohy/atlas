import { z } from 'zod';

import { framework12ResultSchema } from './framework12';
import { overrideResultSchema, section16ResultSchema, trackTypeSchema } from './section16';

export const entryGateResultSchema = z.object({
  ticker: z.string(),
  track: trackTypeSchema,
  dte: z.number().int().nullable(),
  section16: section16ResultSchema,
  framework12: framework12ResultSchema,
  override: overrideResultSchema.nullable(),
});

export type EntryGateResult = z.infer<typeof entryGateResultSchema>;
