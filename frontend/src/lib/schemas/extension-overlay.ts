import { z } from 'zod';

/** Response from GET /api/v1/extension-overlay/{ticker}. */
export const extensionOverlayResponseSchema = z.object({
  ticker: z.string(),

  // Raw metrics — null when insufficient data.
  rsi_14: z.coerce.number().nullable().optional(),
  rsi_7: z.coerce.number().nullable().optional(),
  move_14d_pct: z.coerce.number().nullable().optional(),
  move_21d_pct: z.coerce.number().nullable().optional(),
  pct_above_20dma: z.coerce.number().nullable().optional(),
  pct_above_50dma: z.coerce.number().nullable().optional(),
  pct_above_200dma: z.coerce.number().nullable().optional(),
  week_52_position_pct: z.coerce.number().nullable().optional(),
  gap_today_pct: z.coerce.number().nullable().optional(),
  vwap: z.coerce.number().nullable().optional(),
  pct_vs_vwap: z.coerce.number().nullable().optional(),
  ath: z.coerce.number().nullable().optional(),
  ath_date: z.string().nullable().optional(),
  pct_from_ath: z.coerce.number().nullable().optional(),
  iv_rank: z.coerce.number().nullable().optional(),

  // Deterministic technical sell / exhaustion signals.
  td_setup: z.number().int().nullable().optional(),
  td_setup_direction: z.string().nullable().optional(),
  td_countdown: z.number().int().nullable().optional(),
  td_signal: z.string().nullable().optional(),
  rsi_bearish_divergence: z.boolean().default(false),
  macd_bearish_cross: z.boolean().default(false),

  // Rule-based Elliott Wave + Gann (contextual).
  elliott_wave: z.string().nullable().optional(),
  elliott_direction: z.string().nullable().optional(),
  elliott_signal: z.string().nullable().optional(),
  elliott_confidence: z.number().int().nullable().optional(),
  gann_signal: z.string().nullable().optional(),
  gann_below_1x1: z.boolean().default(false),
  gann_time_cycle_due: z.boolean().default(false),
  gann_nearest_support: z.coerce.number().nullable().optional(),
  gann_nearest_resistance: z.coerce.number().nullable().optional(),

  // Overlay outputs.
  extension_risk_score: z.number().int().min(0),
  extension_flag: z.enum(['GREEN', 'YELLOW', 'RED', 'EXTREME_RED']),
  atlas_score: z.number().int().nullable().optional(),
  action: z
    .enum(['ADD', 'STARTER_WATCH', 'BUY_ON_PULLBACK', 'HOLD_TRIM', 'TRIM_HEDGE', 'AVOID'])
    .nullable()
    .optional(),
  action_detail: z.string().nullable().optional(),

  data_gaps: z.array(z.string()).default([]),
});

export type ExtensionOverlayResponse = z.infer<typeof extensionOverlayResponseSchema>;
export type ExtensionFlag = ExtensionOverlayResponse['extension_flag'];
export type OverlayAction = NonNullable<ExtensionOverlayResponse['action']>;
