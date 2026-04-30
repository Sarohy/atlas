import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const earningsGateSchema = z.object({
  /** Ticker symbol. */
  ticker: z.string(),

  /** Next earnings report date (YYYY-MM-DD) or null when none found. */
  earnings_date: z.string().nullable(),

  /** Date the gate closes (YYYY-MM-DD) or null when no earnings found. */
  gate_close_date: z.string().nullable(),

  /** Calendar days from today to earnings_date. Null when no earnings. */
  days_to_earnings: z.number().int().nullable(),

  /** True when today >= gate_close_date. */
  gate_active: z.boolean(),

  /** Regime-adjusted Framework 1 conviction score (0-100). */
  final_score: z.number().int().min(0).max(100),

  /** True when Framework 8 detects recent significant insider selling. */
  insider_flag: z.boolean(),

  /** True when the investor is permitted to add to the position. */
  can_add: z.boolean(),

  /**
   * Maximum fraction of target weight that may be deployed.
   * 0.0 = no adds, 0.5 = 50% cap, 1.0 = fully open.
   */
  size_cap: z.number().min(0).max(1),

  /**
   * Four possible values: OPEN | CLOSED | 50% CAP | DOUBLE BLOCKED
   */
  status: z.enum(['OPEN', 'CLOSED', '50% CAP', 'DOUBLE BLOCKED']),

  /** Human-readable explanation of the current gate state. */
  message: z.string(),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type EarningsGate = z.infer<typeof earningsGateSchema>;
