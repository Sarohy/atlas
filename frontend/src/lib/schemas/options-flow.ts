import { z } from 'zod';

// ---------------------------------------------------------------------------
// F4 — Options Flow response schema.
//
// Three layers:
//   1. f4_score — OPTIONS-ONLY, time-decayed over 5 sessions (today weighted
//      most). Dark pool no longer enters the score.
//   2. dark_pool_state — the stock-tape "chip" (a state, not a score).
//   3. clearance — the entry decision combining f4_score + the chip.
// ---------------------------------------------------------------------------

export const optionsFlowResponseSchema = z.object({
  ticker: z.string(),

  // Composite (preserved for F9 + Framework Score).
  f4_score: z.number().int().min(0).max(100),
  f4_grade: z.string(),

  // Sub-scores. Null when the corresponding source was unavailable.
  dark_pool_score: z.number().int().min(0).max(100).nullable(),
  options_flow_score: z.number().int().min(0).max(100).nullable(),

  // Signed net flows over the rolling window (USD).
  dark_pool_net_flow_usd: z.number().nullable(),
  options_net_flow_usd: z.number().nullable(),

  // Market-cap context.
  market_cap_usd: z.number().nullable(),
  market_cap_tier: z.string(), // 'LARGE' | 'MID' | 'SMALL'

  // Direction derived from combined net flow.
  flow_direction: z.string(), // 'BULLISH' | 'BEARISH' | 'NEUTRAL'

  // Provenance + data-gap signalling.
  data_source: z.string(), // 'BOTH' | 'DARK_POOL_ONLY' | 'OPTIONS_ONLY' | 'DATA_GAP'
  data_gap_reason: z.string().nullable(),
  lookback_sessions: z.number().int(),

  // Detail counts / extremes (consumed by F9).
  dark_pool_prints_count: z.number().int().min(0),
  dark_pool_large_buy_count: z.number().int().min(0),
  largest_dark_pool_buy_usd: z.number().nullable(),
  largest_options_buy_usd: z.number().nullable(),

  // Layer 2 — stock-tape state ("chip"); Layer 3 — clearance (entry decision).
  dark_pool_state: z
    .enum([
      'FRESH_ACCUMULATION',
      'PERSISTENT_ACCUMULATION',
      'NEUTRAL_MIXED',
      'FADING',
      'ACTIVE_DISTRIBUTION',
      'UNKNOWN',
    ])
    .default('UNKNOWN'),
  dark_pool_state_reason: z.string().nullable().optional(),
  clearance: z.enum(['CLEARED', 'WATCH', 'REVOKED']).default('WATCH'),
  clearance_reason: z.string().nullable().optional(),
});

export type OptionsFlowResponse = z.infer<typeof optionsFlowResponseSchema>;
