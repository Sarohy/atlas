import { z } from 'zod';

const subFactorSchema = z.object({
  score: z.number().int().min(0).max(100),
  source: z.string(),
});

export const forwardGrowthResponseSchema = z.object({
  ticker: z.string(),
  fgs_score: z.number().int().min(0).max(100),
  fgs_grade: z.enum(['ELITE', 'HIGH', 'MODERATE', 'LOW']),
  confidence_pct: z.number().int().min(0).max(100),

  revenue_acceleration: subFactorSchema.extend({
    yoy_pct: z.coerce.number().nullable().optional(),
    accelerating: z.boolean().nullable().optional(),
  }),
  backlog_bookings: subFactorSchema,
  customer_quality: subFactorSchema,
  product_ramp: subFactorSchema,
  tam_bottleneck: subFactorSchema.extend({
    wave: z.string(),
    status: z.string(),
  }),

  // Exact figures from free EDGAR (when disclosed).
  backlog_usd: z.coerce.number().nullable().optional(),
  customer_concentration_pct: z.coerce.number().nullable().optional(),
  customers_over_10pct: z.number().int().nullable().optional(),
  customer_concentration_summary: z.string().nullable().optional(),

  f5_score: z.number().int().nullable().optional(),
  f4_score: z.number().int().nullable().optional(),
  atlas_score: z.number().int().nullable().optional(),
  bucket: z
    .enum(['CORE_COMPOUNDER', 'QUALITY_HOLD', 'GROWTH_TACTICAL', 'STORY_RISK', 'AVOID'])
    .nullable()
    .optional(),
  action: z.string().nullable().optional(),

  data_gaps: z.array(z.string()).default([]),
});

export type ForwardGrowthResponse = z.infer<typeof forwardGrowthResponseSchema>;
export type GrowthBucket = NonNullable<ForwardGrowthResponse['bucket']>;
export type FgsGrade = ForwardGrowthResponse['fgs_grade'];
