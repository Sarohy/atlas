import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export const trancheSizingResponseSchema = z.object({
  /** Ticker symbol (upper-case). */
  ticker: z.string(),

  /** T1 — 10-15% of available cash when initial catalyst confirmed, else Blocked. */
  t1: z.string(),

  /** T2 — 20-25% of available cash when regime is CAUTION, else Blocked. */
  t2: z.string(),

  /** T3 — 30-40% of available cash when regime is CLEAR, else Blocked. */
  t3: z.string(),

  /** T4 — Remaining cash to floor when Iran Resolution confirmed, else Blocked. */
  t4: z.string(),
});

// ---------------------------------------------------------------------------
// Derived type
// ---------------------------------------------------------------------------

export type TrancheSizingResponse = z.infer<typeof trancheSizingResponseSchema>;
