import { z } from 'zod';

// ---------------------------------------------------------------------------
// F4 v2 — Options Flow response schema.
//
// F4 v2 scores a ticker on signed net flows over the trailing 5 trading
// sessions, mapped to 0-100 via a market-cap-tiered anchor table.
// Combination:
//   BOTH           → (dark_pool_score + options_flow_score) / 2
//   DARK_POOL_ONLY → dark_pool_score
//   OPTIONS_ONLY   → options_flow_score
//   DATA_GAP       → 50 (neutral)
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
});

export type OptionsFlowResponse = z.infer<typeof optionsFlowResponseSchema>;
