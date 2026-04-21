import { z } from 'zod';

// ---------------------------------------------------------------------------
// Signal detail schema (Framework 29 AND gate)
// ---------------------------------------------------------------------------

export const signalDetailSchema = z.object({
  /** Signal index (1-5). */
  signal_index: z.number().int().min(1).max(5),
  /** Human-readable signal name. */
  name: z.string(),
  /** Whether this signal is confirmed. */
  confirmed: z.boolean(),
});

export type SignalDetail = z.infer<typeof signalDetailSchema>;

// ---------------------------------------------------------------------------
// Tranche sizing response schema (v7.3.4)
// ---------------------------------------------------------------------------

export const trancheSizingResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  // Concentration cap (Framework 14)
  /** True when position weight >= 8% NAV (concentration cap active). */
  cap_active: z.boolean(),
  /** False when concentration cap suppresses all tranche rows. */
  tranche_display: z.boolean(),
  /** Current position weight as a fraction of NAV (e.g. 0.136 = 13.6%). */
  position_weight: z.number(),
  /** Human-readable status message; present when cap is active. */
  message: z.string().nullable(),

  // AND gate (Framework 29)
  /** True when regime is CLEAR - AND gate applies to T3 and large decisions. */
  and_gate_active: z.boolean(),
  /** True when 3 or more of 5 capitulation signals are confirmed. */
  and_gate_passed: z.boolean(),
  /** Count of AND gate signals confirmed (0-5). */
  signals_confirmed: z.number().int().min(0).max(5),
  /** Per-signal confirmation status for all 5 Framework 29 signals. */
  signals_detail: z.array(signalDetailSchema),

  // Tranche values (null when cap_active is true)
  /** T1 - 10-15% of available cash when catalyst confirmed, Blocked, or null when suppressed. */
  t1: z.string().nullable(),
  /** T2 - 20-25% of available cash when CAUTION, Blocked, or null when suppressed. */
  t2: z.string().nullable(),
  /** T3 - 30-40% when CLEAR + AND gate passes, Blocked, or null when suppressed. */
  t3: z.string().nullable(),
  /** T4 - Remaining cash to floor when Iran confirmed, Blocked, or null when suppressed. */
  t4: z.string().nullable(),

  /** True when T1 has fired for this ticker. T2/T3/T4 are blocked until T1 fires. */
  t1_fired: z.boolean(),
});

// ---------------------------------------------------------------------------
// Derived types
// ---------------------------------------------------------------------------

export type TrancheSizingResponse = z.infer<typeof trancheSizingResponseSchema>;

