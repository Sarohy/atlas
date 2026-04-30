import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const sizingTierSchema = z.enum([
  'CORE_ANCHOR',
  'HIGH_CONVICTION_T2',
  'STANDARD_T2',
  'T3_SATELLITE',
  'CHINA_RISK',
  'HIGH_BETA',
]);

export const concentrationStatusSchema = z.enum([
  'NORMAL',
  'SOFT_CAP',
  'HARD_REVIEW',
  'GRANDFATHERED',
]);

export const clusterStatusSchema = z.enum(['NORMAL', 'YELLOW_ZONE', 'RED_ZONE']);

// ---------------------------------------------------------------------------
// Main response schema
// ---------------------------------------------------------------------------

export const framework14ResultSchema = z.object({
  ticker: z.string(),

  // Position weight
  position_weight_pct: z.number(),
  nav_dollars: z.number(),
  position_dollars: z.number(),

  // Sizing tier
  sizing_tier: sizingTierSchema,
  target_weight_min: z.number(),
  target_weight_max: z.number(),

  // Concentration cap
  concentration_status: concentrationStatusSchema,
  cap_active: z.boolean(),
  soft_cap_breached: z.boolean(),
  hard_review_triggered: z.boolean(),
  grandfathered: z.boolean(),
  grandfathered_expires_at: z.number().nullable(),
  grandfathered_expiry_near: z.boolean(),
  score_display_cap: z.number().int().nullable(),

  // Cluster
  cluster: z.string(),
  cluster_weight_pct: z.number(),
  cluster_status: clusterStatusSchema,
  cluster_yellow_threshold: z.number(),
  cluster_red_threshold: z.number(),

  // Decision outputs
  adds_permitted: z.boolean(),
  trim_recommended: z.boolean(),
  message: z.string(),
});

export const clusterSummaryResultSchema = z.object({
  cluster: z.string(),
  cluster_weight_pct: z.number(),
  cluster_status: clusterStatusSchema,
  cluster_yellow_threshold: z.number(),
  cluster_red_threshold: z.number(),
  tickers: z.array(z.string()),
  trim_recommended: z.boolean(),
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type SizingTier = z.infer<typeof sizingTierSchema>;
export type ConcentrationStatus = z.infer<typeof concentrationStatusSchema>;
export type ClusterStatus = z.infer<typeof clusterStatusSchema>;
export type Framework14Result = z.infer<typeof framework14ResultSchema>;
export type ClusterSummaryResult = z.infer<typeof clusterSummaryResultSchema>;
