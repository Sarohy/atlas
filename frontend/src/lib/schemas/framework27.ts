import { z } from 'zod';

// ---------------------------------------------------------------------------
// Sub-schemas
// ---------------------------------------------------------------------------

export const contagionRuleResultSchema = z.object({
  rule_id: z.number(),
  ticker: z.string(),
  primary_risk: z.string(),
  secondary_exposure: z.string(),
  contagion_trigger_type: z.string(),
  trigger_condition: z.string(),
  triggered: z.boolean(),
  trigger_reason: z.string().default(''),
  action_on_trigger: z.string(),
});

export const framework27ResultSchema = z.object({
  f17_active: z.boolean().nullable(),
  rules_evaluated: z.number(),
  rules_triggered: z.number(),
  triggered_rules: z.array(contagionRuleResultSchema).default([]),
  all_rules: z.array(contagionRuleResultSchema).default([]),
  asia_freight_flagged: z.boolean().default(false),
  metals_disruption_flagged: z.boolean().default(false),
  indium_disruption_flagged: z.boolean().default(false),
  brent_price: z.number().nullable().default(null),
  conflict_duration_days: z.number().nullable().default(null),
  cache_hit: z.boolean().default(false),
  data_as_of: z.string().nullable().default(null),
});

export const manualFlagRequestSchema = z.object({
  trigger_type: z.enum([
    'ASIA_FREIGHT_DISRUPTION_PCT',
    'METALS_DISRUPTION',
    'INDIUM_SUPPLY_DISRUPTION',
  ]),
  flagged_by: z.string().min(1).max(100),
  notes: z.string().nullable().default(null),
  override_reason: z.string().min(50),
});

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export type ContagionRuleResult = z.infer<typeof contagionRuleResultSchema>;
export type Framework27Result = z.infer<typeof framework27ResultSchema>;
export type ManualFlagRequest = z.infer<typeof manualFlagRequestSchema>;
