import { z } from 'zod';

/** Response from GET /api/v1/extension-washout/{ticker}. Display/posture only. */
export const extensionWashoutResponseSchema = z.object({
  ticker: z.string(),

  // Headline posture (§9).
  state: z.enum([
    'STOP_ADD',
    'ARM_PROTECTION',
    'ACTIVE_PROTECTION',
    'HEDGE',
    'TRIM_WATCH',
    'TRIM',
    'FORCED_DE_RISK_REVIEW',
    'BOOK_LEVEL_HEDGE',
    'WAIT',
  ]),
  reason: z.string(),
  rung: z.string(),

  // Per-name tags (§2 / §3.2).
  track: z.string(),
  overshoot: z.string(),
  low_confidence: z.boolean(),

  // Trim authorization (§7) + size rule (§3.1).
  trim_authorized: z.boolean(),
  size_relabeled: z.boolean(),
  confirmation_count: z.number().int(),
  confirmation_present: z.array(z.string()).default([]),

  // Confirmation-leg inputs.
  flow_distribution: z.boolean().default(false),
  vwap_lost: z.boolean().default(false),
  group_rolling: z.boolean().default(false),
  absorption: z.boolean().default(false),
  hard_override: z.boolean().default(false),
  negative_catalyst: z.boolean().default(false),

  // Extension metrics (read-only).
  dist_50d: z.coerce.number().nullable().optional(),
  rsi_14: z.coerce.number().nullable().optional(),
  move_21d_pct: z.coerce.number().nullable().optional(),
  move_14d_pct: z.coerce.number().nullable().optional(),
  move_20d_pct: z.coerce.number().nullable().optional(),
  dark_pool_sell_pct: z.coerce.number().nullable().optional(),
  metric_legs: z
    .object({ moderate: z.array(z.string()).default([]), extreme: z.array(z.string()).default([]) })
    .default({ moderate: [], extreme: [] }),

  // Position sizing (§3.1).
  position_weight_pct: z.coerce.number().nullable().optional(),
  target_pct: z.coerce.number(),
  below_target: z.boolean().nullable().optional(),

  // Breadth (§5).
  breadth: z.string().nullable().optional(),
  breadth_watch_count: z.number().int().default(0),
  breadth_hedge_count: z.number().int().default(0),
  breadth_universe_size: z.number().int().default(0),

  // Overshoot Elasticity (SPEC v2.1).
  elasticity_tier: z
    .enum(['EXTREME', 'HIGH', 'MODERATE', 'LOW', 'SHARP_FALLER', 'NEVER_CROSS', 'ANOMALY', 'UNKNOWN'])
    .default('UNKNOWN'),
  elasticity_score: z.coerce.number().nullable().optional(),
  elasticity_confidence: z.string().default('LOW'),
  elasticity_event_count: z.number().int().default(0),
  plus40_state: z.string().default('ARM_PROTECTION'),
  plus40_behavior: z.string().default(''),
  elasticity_ladder: z.array(z.coerce.number()).default([]),
  sizing_guidance: z.string().default(''),
  elasticity_provisional: z.boolean().default(false),
  elasticity_watch_promote: z.boolean().default(false),
  elasticity_excluded_from_recalibration: z.boolean().default(false),
  elasticity_hard_override: z.boolean().default(false),
  rv20: z.coerce.number().nullable().optional(),
  rv60: z.coerce.number().nullable().optional(),
  beta: z.coerce.number().nullable().optional(),
  elasticity_data_gaps: z.array(z.string()).default([]),

  data_gaps: z.array(z.string()).default([]),
});

export type ExtensionWashoutResponse = z.infer<typeof extensionWashoutResponseSchema>;
export type WashoutState = ExtensionWashoutResponse['state'];
