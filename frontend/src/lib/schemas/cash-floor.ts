import { z } from 'zod';

// ---------------------------------------------------------------------------
// FloorStatus enum
// ---------------------------------------------------------------------------

export const floorStatusSchema = z.enum([
  'HEALTHY',
  'LOW_BUFFER',
  'AT_FLOOR',
  'BELOW_FLOOR',
  'CRITICAL_ZERO',
]);

export type FloorStatus = z.infer<typeof floorStatusSchema>;

// ---------------------------------------------------------------------------
// Framework5Response — portfolio-level (new GET /cash-floor/status endpoint)
// ---------------------------------------------------------------------------

export const framework5ResponseSchema = z.object({
  /** Active regime: CLEAR | SOFT CAUTION | CAUTION | CRISIS HALT */
  regime: z.string(),
  /** Brent crude price at evaluation time. */
  brent_price: z.number().nullable(),
  /** CBOE VIX level at evaluation time. */
  vix_value: z.number().nullable(),
  /** Active floor fraction (e.g. 0.20 = 20%). */
  floor_pct: z.number(),
  /** Human-readable floor label, e.g. '30%+' or '10% (transition — 7 days)'. */
  floor_pct_display: z.string(),
  /** Minimum cash floor in USD. */
  floor_amount: z.number(),
  /** Total portfolio NAV in USD. */
  total_nav: z.number(),
  /** Current cash balance in USD. */
  total_cash: z.number(),
  /** Cash as a fraction of NAV. */
  cash_pct: z.number(),
  /** Cash above floor in USD (0 when below floor). */
  buffer: z.number(),
  /** Buffer as fraction of NAV. */
  buffer_pct: z.number(),
  /** Deployable cash above floor in USD. */
  available_above_floor: z.number(),
  /** Shortfall below floor in USD (0 when healthy). */
  shortfall: z.number(),
  /** True when cash < floor. */
  is_below_floor: z.boolean(),
  /** Categorised floor status. */
  floor_status: floorStatusSchema,
  /** NONE | AMBER | CRITICAL */
  warning_level: z.string(),
  /** Warning text when applicable, null when NONE. */
  warning_message: z.string().nullable(),
  /** False when cash is at or below the floor. */
  deployment_permitted: z.boolean(),
  /** True during the 2-week CLEAR transition period. */
  transition_active: z.boolean(),
  /** Transition floor (0.10) when active, null otherwise. */
  transition_floor_pct: z.number().nullable(),
  /** Days until floor drops to 8%; null when not transitioning. */
  days_until_settled: z.number().nullable(),
  /** ISO date when CLEAR regime started; null when not CLEAR. */
  clear_transition_date: z.string().nullable(),
  /** Portfolio weighted beta × (1 − cash_pct). */
  effective_beta: z.number(),
  /** Target effective beta (1.75 per ATLAS spec). */
  target_beta: z.number(),
  /** NORMAL | ELEVATED | CRITICAL */
  beta_status: z.string(),
  /** True when no breach used this quarter. */
  floor_breach_available: z.boolean(),
  /** Breaches used this quarter. */
  breach_count_this_quarter: z.number(),
  /** Regime floor rationale. */
  rationale: z.string(),
});

export type Framework5Response = z.infer<typeof framework5ResponseSchema>;

// ---------------------------------------------------------------------------
// Legacy per-ticker schema — GET /cash-floor/{ticker}
// ---------------------------------------------------------------------------

export const cashFloorResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  /** Framework 2 rule that fired: 1=CRISIS HALT, 2=CAUTION, 3=SOFT CAUTION, 4=CLEAR. null = no rule. */
  rule_triggered: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).nullable(),

  /** Brent crude price in USD per barrel at evaluation time. */
  brent_price: z.number().nullable(),

  /** CBOE VIX index level at evaluation time. */
  vix_value: z.number().nullable(),

  /** Regime condition: CRISIS | CAUTION | CLEAR | FULLY_DEPLOYED */
  condition: z.string(),

  /** Human-readable rationale for the floor requirement. */
  rationale: z.string(),

  /** Minimum cash floor as a fraction of position value (e.g. 0.35 = 35%). */
  floor_pct_min: z.number(),

  /** Maximum cash floor as a fraction of position value. */
  floor_pct_max: z.number(),

  /** Current portfolio position value in USD — null when ticker not in portfolio. */
  position_value_usd: z.number().nullable(),

  /** Minimum cash to hold in USD — null when ticker not in portfolio. */
  floor_usd_min: z.number().nullable(),

  /** Maximum cash to hold in USD — null when ticker not in portfolio. */
  floor_usd_max: z.number().nullable(),

  /** Current portfolio cash balance in USD. */
  cash_balance: z.number().nullable(),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type CashFloorResponse = z.infer<typeof cashFloorResponseSchema>;
