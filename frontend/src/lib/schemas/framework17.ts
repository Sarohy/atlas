import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const geoFlagStateSchema = z.enum([
  'NONE',
  'DE_ESCALATING',
  'ACTIVE',
  'NOT_SET',
]);

export const f17SeveritySchema = z.enum([
  'CRITICAL',
  'HIGH',
  'ELEVATED',
  'NONE',
  'UNKNOWN',
]);

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const framework17SimpleResultSchema = z.object({
  f17_active: z.boolean().nullable(),
  flag_state: geoFlagStateSchema,
  clear_regime_possible: z.boolean(),
  severity: f17SeveritySchema,
  brent_price: z.number().nullable(),
  conflict_duration_days: z.number().nullable(),
});

export const framework17ResultSchema = z.object({
  f17_active: z.boolean().nullable(),
  flag_state: geoFlagStateSchema,
  clear_regime_possible: z.boolean(),
  severity: f17SeveritySchema,
  brent_price: z.number().nullable(),
  conflict_duration_days: z.number().nullable(),
  set_by: z.string().nullable().default(null),
  set_at: z.string().nullable().default(null),
  conflict_start_date: z.string().nullable().default(null),
  notes: z.string().nullable().default(null),
  session_date: z.string().nullable().default(null),
  carried_forward: z.boolean().default(false),
  regime: z.string().nullable().default(null),
  regime_available: z.boolean().default(false),
  clear_regime_blocked: z.boolean().default(false),
  briefing_message: z.string().default(''),
  briefing_urgency: z.string().default('INFO'),
  cache_hit: z.boolean().default(false),
  data_as_of: z.string().nullable().default(null),
});

export const flagHistoryEntrySchema = z.object({
  id: z.number(),
  flag_state: geoFlagStateSchema,
  set_by: z.string(),
  set_at: z.string(),
  conflict_start_date: z.string().nullable(),
  notes: z.string().nullable(),
  session_date: z.string(),
});

export const setFlagRequestSchema = z.object({
  flag_state: geoFlagStateSchema.exclude(['NOT_SET']),
  set_by: z.string().min(1).max(100),
  conflict_start_date: z.string().nullable().default(null),
  notes: z.string().nullable().default(null),
  override_reason: z.string().min(50),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type GeoFlagState = z.infer<typeof geoFlagStateSchema>;
export type F17Severity = z.infer<typeof f17SeveritySchema>;
export type Framework17SimpleResult = z.infer<typeof framework17SimpleResultSchema>;
export type Framework17Result = z.infer<typeof framework17ResultSchema>;
export type FlagHistoryEntry = z.infer<typeof flagHistoryEntrySchema>;
export type SetFlagRequest = z.infer<typeof setFlagRequestSchema>;
