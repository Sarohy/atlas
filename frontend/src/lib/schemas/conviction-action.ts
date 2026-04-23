import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums (v7.3.4 Watchlist Tier Structure)
// ---------------------------------------------------------------------------

export const tierSchema = z.enum([
  'TIER_1_CORE',
  'GREY_ZONE',
  'TIER_2',
  'TIER_3',
  'WATCHLIST',
]);

export const positionSizeStatusSchema = z.enum([
  'UNDERWEIGHT',
  'IN_RANGE',
  'OVERWEIGHT',
  'NO_POSITION',
]);

export const consensusStatusSchema = z.enum([
  'NOT_REQUIRED',
  'PENDING',
  'CONFIRMED',
  'FAILED',
]);

// ---------------------------------------------------------------------------
// Response schema
// ---------------------------------------------------------------------------

export const convictionActionResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  /** Regime-adjusted Framework Score (0-100). */
  final_score: z.number(),

  /** Conviction tier key. */
  tier: tierSchema,

  /** Human-readable tier label (e.g. "TIER 1 — CORE"). */
  tier_label: z.string(),

  /** CSS hex color for this tier (e.g. "#39d353"). */
  tier_color: z.string(),

  /** Lower bound of score band for this tier (inclusive). */
  score_band_min: z.number().int(),

  /** Upper bound of score band for this tier (inclusive). Null for TIER_1_CORE (no ceiling). */
  score_band_max: z.number().int().nullable(),

  /** Minimum position size as a percentage of NAV (e.g. 3.0 = 3%). */
  size_min_pct: z.number(),

  /** Maximum position size as a percentage of NAV (e.g. 5.0 = 5%). */
  size_max_pct: z.number(),

  /** Recommended action text. */
  action: z.string(),

  /** Whether LEAPS options are eligible (TIER_1_CORE only). */
  leaps_eligible: z.boolean(),

  /** Whether 3-AI consensus is required before adding (GREY_ZONE only). */
  consensus_required: z.boolean(),

  /** Current consensus status. */
  consensus_status: consensusStatusSchema,

  /** Current position weight as a percentage of NAV. */
  current_weight_pct: z.number(),

  /** Whether the position is underweight, in range, overweight, or not held. */
  position_size_status: positionSizeStatusSchema,

  /** Room to add before hitting the size ceiling, as a percentage of NAV. */
  room_to_add_pct: z.number(),

  /** Whether the position size exceeds the tier maximum. */
  trim_suggested: z.boolean(),

  /** Whether new adds are currently permitted. */
  adds_permitted: z.boolean(),

  /** Reason adds are blocked, or null if adds are permitted. */
  adds_blocked_reason: z.string().nullable(),

  /** Whether Framework 13 beta cap is currently active. */
  beta_cap_active: z.boolean(),

  /** Whether Framework 14 concentration cap is currently active. */
  concentration_cap: z.boolean(),

  /** Whether the exit rule has been triggered (2 consecutive closes < 55). */
  exit_triggered: z.boolean(),

  /** Number of consecutive Friday closes below 55. */
  exit_cycle_count: z.number().int(),

  /** Cluster name this ticker belongs to. */
  cluster: z.string(),

  /** Cluster total weight as a percentage of NAV. */
  cluster_weight_pct: z.number(),

  /** Cluster status label (e.g. "OK", "OVERWEIGHT"). */
  cluster_status: z.string(),

  /** One-line bottom rationale / action message. */
  rationale: z.string(),
});

// ---------------------------------------------------------------------------
// Consensus update request schema
// ---------------------------------------------------------------------------

export const consensusUpdateRequestSchema = z.object({
  status: consensusStatusSchema,
});

// ---------------------------------------------------------------------------
// Exit cycle response schema
// ---------------------------------------------------------------------------

export const exitCycleResponseSchema = z.object({
  ticker: z.string(),
  exit_cycle_count: z.number().int(),
  exit_triggered: z.boolean(),
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type Tier = z.infer<typeof tierSchema>;
export type PositionSizeStatus = z.infer<typeof positionSizeStatusSchema>;
export type ConsensusStatus = z.infer<typeof consensusStatusSchema>;
export type ConvictionActionResponse = z.infer<typeof convictionActionResponseSchema>;
export type ConsensusUpdateRequest = z.infer<typeof consensusUpdateRequestSchema>;
export type ExitCycleResponse = z.infer<typeof exitCycleResponseSchema>;
