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
  // Hedge-structure context flag — tagged separately, never rewrites f4_score.
  hedge_structure: z
    .enum([
      'DIRECTIONAL_BEARISH',
      'PROTECTIVE_HEDGE',
      'HEDGED_BULLISH',
      'PUT_SELLING',
      'BULLISH',
      'MIXED',
      'NONE',
    ])
    .default('NONE'),
  hedge_structure_reason: z.string().nullable().optional(),
  bullish_share: z.number().nullable().optional(),
  f4_state: z.string().default('Neutral'),
  f4_add_impact: z.string().default('No edge — no fresh add from F4b'),
  dark_pool_confidence: z.string().default('No dark-pool data'),
  // Multi-window F4b (current-session-weighted) — Multi-Window Pull Spec.
  live_tape_state: z.string().default('Data gap'),
  persistence_state: z.string().default('Neutral / constructive'),
  current_session_net_usd: z.number().nullable().optional(),
  otm_call_ask_usd: z.number().nullable().optional(),
  otm_put_ask_usd: z.number().nullable().optional(),
  raw_bull_premium_usd: z.number().nullable().optional(),
  raw_bear_premium_usd: z.number().nullable().optional(),
  raw_bullish_share: z.number().nullable().optional(),
  raw_largest_bullish_print_usd: z.number().nullable().optional(),
  raw_largest_call_ask_print_usd: z.number().nullable().optional(),
  declassified_premium_by_reason: z.record(z.string(), z.number()).optional(),
  adjusted_bull_premium_usd: z.number().nullable().optional(),
  adjusted_bear_premium_usd: z.number().nullable().optional(),
  adjusted_bullish_share: z.number().nullable().optional(),
  adjusted_largest_bullish_print_usd: z.number().nullable().optional(),
  f4b_score_input_source: z.string().optional(),
  f4b_universe_source: z.string().optional(),
  // Source confidence in the official F4 universe: FULL (broad tape) |
  // PROVISIONAL (narrow flagged-alert universe) | NO_DATA. f4b_provisional is
  // true whenever the score is degraded-source and must not read as confident.
  f4b_source_confidence: z.string().default('NO_DATA'),
  f4b_source_confidence_reason: z.string().default(''),
  f4b_provisional: z.boolean().default(false),
  // Full-tape candidate (diagnostic) — FULL-coverage read scored in parallel,
  // shown beside the authoritative provisional alert score for validation.
  f4b_full_tape_score: z.number().int().min(0).max(100).nullable().default(null),
  f4b_full_tape_source: z.string().default('NONE'),
  f4b_full_tape_confidence: z.string().default('NO_DATA'),
  f4b_full_tape_bullish_share: z.number().nullable().default(null),
  f4b_full_tape_net_flow_usd: z.number().nullable().default(null),
  f4b_universe_total_alerts: z.number().int().nonnegative().optional(),
  f4b_universe_directional_alerts: z.number().int().nonnegative().optional(),
  f4b_universe_excluded_alerts: z.number().int().nonnegative().optional(),
  raw_call_ask_premium_usd: z.number().nullable().optional(),
  raw_call_bid_premium_usd: z.number().nullable().optional(),
  raw_put_ask_premium_usd: z.number().nullable().optional(),
  raw_put_bid_premium_usd: z.number().nullable().optional(),
  live_pulse_score: z.number().int().min(0).max(100).nullable().optional(),
  live_pulse_state: z.string().optional(),
  // Flow Monitor — the final action gate (only add authority).
  flow_monitor_action: z.string().default('WATCH'),
  flow_monitor_reason: z.string().nullable().optional(),
});

export type OptionsFlowResponse = z.infer<typeof optionsFlowResponseSchema>;
