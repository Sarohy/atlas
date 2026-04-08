import { z } from 'zod';

import { tickerResponseSchema } from '@/lib/schemas/ticker';

export const clusterCreateSchema = z.object({
  name: z.string().min(1).max(100),
  /** Hex colour, exactly 7 chars, e.g. '#4a90d9'. */
  color: z
    .string()
    .length(7)
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Must be a valid hex colour (#RRGGBB)'),
});

export const clusterUpdateSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  color: z
    .string()
    .length(7)
    .regex(/^#[0-9A-Fa-f]{6}$/)
    .optional(),
});

export const clusterResponseSchema = z.object({
  id: z.number(),
  name: z.string(),
  color: z.string(),
  tickers: z.array(tickerResponseSchema).default([]),
  created_at: z.string(),
  updated_at: z.string(),
});

export type ClusterCreate = z.infer<typeof clusterCreateSchema>;
export type ClusterUpdate = z.infer<typeof clusterUpdateSchema>;
export type ClusterResponse = z.infer<typeof clusterResponseSchema>;
