import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const signalStatusSchema = z.enum([
  'CONFIRMED',
  'NOT_MET',
  'UNAVAILABLE',
  'MANUAL_REQUIRED',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const framework29SignalSchema = z.object({
  signal_number: z.number().int().min(1).max(5),
  signal_name: z.string(),
  status: signalStatusSchema,
  confirmed: z.boolean(),
  data_missing: z.boolean(),
  missing_reason: z.string().nullable(),
  current_values: z.record(z.string(), z.unknown()),
  threshold: z.record(z.string(), z.unknown()),
});

// ---------------------------------------------------------------------------
// Main result schemas
// ---------------------------------------------------------------------------

export const framework29ResultSchema = z.object({
  signals_confirmed: z.number().int(),
  signals_unavailable: z.number().int(),
  and_gate_passed: z.boolean(),
  gate_status: z.string(),
  gate_message: z.string(),
  signals: z.array(framework29SignalSchema),
  data_gap_severity: z.string(),
  warning_messages: z.array(z.string()),
  last_updated: z.string(),
  data_age_minutes: z.number(),
  cache_hit: z.boolean(),
});

export const framework29GateStatusSchema = z.object({
  and_gate_passed: z.boolean(),
  signals_confirmed: z.number().int(),
  signals_unavailable: z.number().int(),
  gate_status: z.string(),
  data_gap_severity: z.string(),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type SignalStatus = z.infer<typeof signalStatusSchema>;
export type Framework29Signal = z.infer<typeof framework29SignalSchema>;
export type Framework29Result = z.infer<typeof framework29ResultSchema>;
export type Framework29GateStatus = z.infer<typeof framework29GateStatusSchema>;
