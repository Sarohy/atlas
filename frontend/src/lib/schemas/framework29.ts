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
  signal_number: z.number().int().min(1).max(4),
  signal_name: z.string(),
  status: signalStatusSchema,
  confirmed: z.boolean(),
  data_missing: z.boolean(),
  missing_reason: z.string().nullable(),
  current_values: z.record(z.string(), z.unknown()),
  threshold: z.record(z.string(), z.unknown()),
});

// ---------------------------------------------------------------------------
// Main result schemas (flat counter — backward compat)
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
  crisis_halt_blocked: z.boolean().default(false),
});

export const framework29GateStatusSchema = z.object({
  and_gate_passed: z.boolean(),
  signals_confirmed: z.number().int(),
  signals_unavailable: z.number().int(),
  gate_status: z.string(),
  data_gap_severity: z.string(),
  crisis_halt_blocked: z.boolean().default(false),
});

// ---------------------------------------------------------------------------
// F29 Three-Path Entry Classifier schemas (per-ticker)
// ---------------------------------------------------------------------------

const conditionMetSchema = z.union([z.boolean(), z.literal('UNAVAILABLE')]);

export const f29EntryTypeSchema = z.enum([
  'WASHOUT',
  'CATALYST_VALIDATED',
  'DISCRETIONARY',
  'BLOCKED_BY_REGIME',
  'UNAVAILABLE',
]);

export const f29GateStatusSchema = z.enum(['PASS', 'BLOCKED', 'UNAVAILABLE']);

const f29ConditionResultSchema = z.object({
  id: z.string(),
  met: conditionMetSchema,
  value: z.number().nullable(),
  reason: z.string().nullable(),
});

export const f29RegimePreconditionSchema = z.object({
  regime: z.string(),
  passed: z.boolean(),
  reason: z.string().nullable(),
  regime_undefined_flag: z.boolean(),
});

export const f29WashoutEvaluationSchema = z.object({
  matched: z.boolean(),
  session_change_pct: z.number().nullable(),
  f4_score: z.number().nullable(),
  conditions: z.array(f29ConditionResultSchema),
  data_gaps: z.array(z.string()),
});

export const f29CatalystValidatedEvaluationSchema = z.object({
  matched: z.boolean(),
  position_held: conditionMetSchema,
  score_tier_pass: conditionMetSchema,
  sub_conditions: z.array(f29ConditionResultSchema),
  sub_conditions_met_count: z.number().int(),
  data_gaps: z.array(z.string()),
});

const f29DiscretionarySignalSchema = z.object({
  id: z.string(),
  label: z.string(),
  met: conditionMetSchema,
  value: z.number().nullable(),
});

export const f29DiscretionaryEvaluationSchema = z.object({
  signals: z.array(f29DiscretionarySignalSchema),
  signals_met: z.number().int(),
  signals_unavailable: z.number().int(),
  threshold: z.number().int(),
  threshold_inferred: z.boolean(),
});

export const f29EvaluationSchema = z.object({
  framework_id: z.literal(29),
  ticker: z.string(),
  gate_status: f29GateStatusSchema,
  entry_type: f29EntryTypeSchema,
  regime_precondition: f29RegimePreconditionSchema,
  washout_evaluation: f29WashoutEvaluationSchema,
  catalyst_validated_evaluation: f29CatalystValidatedEvaluationSchema,
  discretionary_evaluation: f29DiscretionaryEvaluationSchema.nullable(),
  decision_trace_id: z.string(),
  evaluated_at: z.string(),
  all_data_gaps: z.array(z.string()),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type SignalStatus = z.infer<typeof signalStatusSchema>;
export type Framework29Signal = z.infer<typeof framework29SignalSchema>;
export type Framework29Result = z.infer<typeof framework29ResultSchema>;
export type Framework29GateStatus = z.infer<typeof framework29GateStatusSchema>;

export type F29EntryType = z.infer<typeof f29EntryTypeSchema>;
export type F29GateStatus = z.infer<typeof f29GateStatusSchema>;
export type F29RegimePrecondition = z.infer<typeof f29RegimePreconditionSchema>;
export type F29WashoutEvaluation = z.infer<typeof f29WashoutEvaluationSchema>;
export type F29CatalystValidatedEvaluation = z.infer<typeof f29CatalystValidatedEvaluationSchema>;
export type F29DiscretionaryEvaluation = z.infer<typeof f29DiscretionaryEvaluationSchema>;
export type F29Evaluation = z.infer<typeof f29EvaluationSchema>;
