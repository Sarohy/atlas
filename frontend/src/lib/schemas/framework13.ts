import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const betaSourceSchema = z.enum(['CONFIRMED', 'CALCULATED', 'DEFAULT']);

export const sizingTierSchema = z.enum([
  'CHINA_RISK',
  'AAOI_TYPE_HIGH_BETA',
  'VERY_HIGH_BETA',
  'HIGH_BETA',
  'MODERATE_BETA',
  'LOW_BETA',
]);

// ---------------------------------------------------------------------------
// Main response schema — mirrors backend Framework13Result Pydantic model
// ---------------------------------------------------------------------------

export const framework13ResultSchema = z.object({
  ticker: z.string(),
  beta: z.number(),
  beta_source: betaSourceSchema,
  position_weight_pct: z.number(),
  position_dollars: z.number(),
  effective_exposure_pct: z.number(),
  effective_exposure_note: z.string(),
  beta_cap_active: z.boolean(),
  beta_cap_limit_pct: z.number().nullable(),
  beta_cap_reason: z.string().nullable(),
  sizing_tier: sizingTierSchema,
  max_weight_pct: z.number(),
  adds_permitted: z.boolean(),
  warning_level: z.string(),
  warning_message: z.string().nullable(),
  beta_source_flag: z.boolean(),
});

// ---------------------------------------------------------------------------
// Portfolio beta schemas — mirrors backend PortfolioBetaResult Pydantic model
// ---------------------------------------------------------------------------

export const portfolioPositionBetaSchema = z.object({
  ticker: z.string(),
  weight: z.number(),
  beta: z.number(),
  contribution: z.number(),
  source: betaSourceSchema,
});

export const portfolioBetaResultSchema = z.object({
  weighted_avg_beta: z.number(),
  effective_beta: z.number(),
  cash_percentage: z.number(),
  target_beta: z.number(),
  beta_status: z.string(),
  warning_level: z.string(),
  warning_message: z.string().nullable(),
  position_betas: z.array(portfolioPositionBetaSchema),
});

// ---------------------------------------------------------------------------
// TypeScript types derived from schemas
// ---------------------------------------------------------------------------

export type BetaSource = z.infer<typeof betaSourceSchema>;
export type SizingTier = z.infer<typeof sizingTierSchema>;
export type Framework13Result = z.infer<typeof framework13ResultSchema>;
export type PortfolioPositionBeta = z.infer<typeof portfolioPositionBetaSchema>;
export type PortfolioBetaResult = z.infer<typeof portfolioBetaResultSchema>;
