import { z } from 'zod';

export const geopoliticalStateSchema = z.enum([
  'NONE',
  'RESOLVED',
  'DE_ESCALATING',
  'ACTIVE_RISK',
  'ESCALATING',
]);
export type GeopoliticalState = z.infer<typeof geopoliticalStateSchema>;

// ---------------------------------------------------------------------------
// Top-level response schema
// ---------------------------------------------------------------------------

export const regimeModifierResponseSchema = z.object({
  /** Ticker symbol (upper-case) */
  ticker: z.string(),

  /** Morning briefing geopolitical gate shared across the app */
  geopolitical_state: geopoliticalStateSchema,

  /** Brent crude price in USD per barrel (most recent daily close), or null */
  brent_price: z.number().nullable(),

  /** CBOE VIX index level (most recent daily close), or null */
  vix_value: z.number().nullable(),

  /** Number of consecutive most recent Brent closes below $95 */
  brent_consecutive_below_95_count: z.number().int().min(0),

  /** Original Framework Score before regime adjustment 0–100 */
  base_score: z.number().int().min(0).max(100),

  /** Score after applying the triggered regime rule 0–100 */
  adjusted_score: z.number().int().min(0).max(100),

  /**
   * Which rule fired: 1 = Crisis Halt, 2 = Caution, 3 = Soft Caution, 4 = Clear.
   * null when normal market conditions — no rule triggered.
   */
  rule_triggered: z.union([
    z.literal(1),
    z.literal(2),
    z.literal(3),
    z.literal(4),
  ]).nullable(),

  /** Human-readable name of the triggered rule, e.g. CRISIS | CAUTION | CLEAR | NORMAL. */
  rule: z.string(),

  /** Displayed regime after applying the geopolitical gate. */
  effective_regime: z.string(),

  /** Score delta applied by the triggered rule: -10, -5, -3, +5, or 0. */
  modifier: z.number().int(),

  /** Minimum required cash as a fraction of position value (0.35 = 35%) */
  min_cash_pct: z.number(),

  /** Maximum recommended cash as a fraction of position value (0.40 = 40%) */
  max_cash_pct: z.number(),

  /** Minimum cash in USD — null when ticker is not in the portfolio */
  min_cash_usd: z.number().nullable(),

  /** Maximum cash in USD — null when ticker is not in the portfolio */
  max_cash_usd: z.number().nullable(),

  /** Human-readable cash management instruction from the triggered rule */
  output_text: z.string(),

  /** Explanation of how the regime was determined. */
  determination_text: z.string(),

  // ── Enriched condition display (Section 14 spec v2.1) ─────────────────

  /** Brent price with zone label, e.g. '$97.50 — $95-110 (CAUTION trigger)'. */
  brent_condition: z.string().default(''),

  /** VIX level with zone label, e.g. '17.48 — Below 22 (SOFT CAUTION zone)'. */
  vix_condition: z.string().default(''),

  /** Active geopolitical flag value, e.g. 'ACTIVE_RISK'. */
  geo_condition: z.string().default(''),

  /** Whether this regime uses OR or AND logic. */
  trigger_logic: z.string().default(''),

  /** Explanation of the modifier applied, e.g. 'CAUTION + Escalating geo → −7'. */
  modifier_reason: z.string().default(''),

  /** True only when regime=CAUTION and geo=ESCALATING (−7 modifier). */
  special_case_active: z.boolean().default(false),

  /** Minimum portfolio cash floor fraction per Section 14.1 (0.08 = 8%). */
  cash_floor_pct: z.number().default(0.2),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type RegimeModifierResponse = z.infer<typeof regimeModifierResponseSchema>;
