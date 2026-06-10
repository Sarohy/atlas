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

  // Overlay outputs.
  extension_risk_score: z.number().int().min(0),
  extension_flag: z.enum(['GREEN', 'YELLOW', 'RED', 'EXTREME_RED']),
  atlas_score: z.number().int().nullable().optional(),
  action: z
    .enum(['ADD', 'BUY_ON_PULLBACK', 'HOLD_TRIM', 'TRIM_HEDGE', 'AVOID'])
    .nullable()
    .optional(),
  action_detail: z.string().nullable().optional(),

  data_gaps: z.array(z.string()).default([]),
});

export type ExtensionOverlayResponse = z.infer<typeof extensionOverlayResponseSchema>;
export type ExtensionFlag = ExtensionOverlayResponse['extension_flag'];
export type OverlayAction = NonNullable<ExtensionOverlayResponse['action']>;
