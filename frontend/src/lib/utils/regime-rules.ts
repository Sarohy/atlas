// ---------------------------------------------------------------------------
// Regime Rule Constants — mirror backend/src/atlas/services/regime_modifier_service.py
// ---------------------------------------------------------------------------

// Rule 1 — Crisis Halt thresholds
export const RULE1_BRENT_THRESHOLD = 110.0;
export const RULE1_VIX_THRESHOLD = 35.0;
export const RULE1_SCORE_DELTA = -10;
export const RULE1_MIN_CASH_PCT = 0.35;
export const RULE1_MAX_CASH_PCT = 0.4;

// Rule 2 — Caution thresholds
export const RULE2_BRENT_LOW = 95.0;
export const RULE2_BRENT_HIGH = 110.0;
export const RULE2_VIX_LOW = 24.0;
export const RULE2_VIX_HIGH = 35.0;
export const RULE2_SCORE_DELTA = -5;
export const RULE2_SCORE_DELTA_ESCALATING = -7; // ONLY special case in 16-row table
export const RULE2_MIN_CASH_PCT = 0.25;
export const RULE2_MAX_CASH_PCT = 0.35;

// Rule 3 — Soft Caution thresholds
export const RULE3_BRENT_THRESHOLD = 100.0;
export const RULE3_VIX_THRESHOLD = 22.0;
export const RULE3_SCORE_DELTA = -3;
export const RULE3_MIN_CASH_PCT = 0.15;
export const RULE3_MAX_CASH_PCT = 0.25;

// Rule 4 — Clear thresholds
export const RULE4_BRENT_CLEAR = 95.0;
export const RULE4_VIX_CLEAR = 24.0;
export const RULE4_SCORE_DELTA = 5;
export const RULE4_MIN_CASH_PCT = 0.1;
export const RULE4_MAX_CASH_PCT = 0.12;

// Cash floors per regime (Section 14.1)
export const CASH_FLOOR_RULE1 = 0.30; // CRISIS HALT
export const CASH_FLOOR_RULE2 = 0.20; // CAUTION
export const CASH_FLOOR_RULE3 = 0.15; // SOFT CAUTION
export const CASH_FLOOR_RULE4 = 0.08; // CLEAR

// Consecutive Brent closes required for Rule 4
const BRENT_NUM_CLOSES = 2;

// Score bounds
const MIN_SCORE = 0;
const MAX_SCORE = 100;

// Output text — matches spec verbatim
const OUTPUT_RULE1 = 'must stay in cash\ncannot be touched\nfor any trade';
const OUTPUT_RULE2 = 'must stay in cash';
const OUTPUT_RULE2_ESCALATING = 'must stay in cash\nGEO PENALTY ACTIVE: CAUTION + ESCALATING';
const OUTPUT_RULE3 = 'reduce exposure\nmonitor conditions closely';
const OUTPUT_RULE4 = 'only this stays in cash\neverything else\ncan be deployed';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RegimeRule = 1 | 2 | 3 | 4;
export type AutomaticRegimeLabel = 'CRISIS HALT' | 'CAUTION' | 'SOFT CAUTION' | 'CLEAR';
export type EffectiveRegimeLabel = AutomaticRegimeLabel;

// GeopoliticalState mirrors the 5-state enum in lib/schemas/regime-modifier.ts
export type GeopoliticalState =
  | 'NONE'
  | 'RESOLVED'
  | 'DE_ESCALATING'
  | 'ACTIVE_RISK'
  | 'ESCALATING';

export type RegimeOutput = {
  ruleTriggered: RegimeRule | null;
  adjustedScore: number;
  minCashPct: number;
  maxCashPct: number;
  outputText: string;
};

// ---------------------------------------------------------------------------
// Pure functions — no I/O, no side effects, fully unit-testable
// ---------------------------------------------------------------------------

/**
 * Return the highest-priority regime rule that fires, or null.
 *
 * REGIME is determined by Brent + VIX alone (Section 14.1, KEY RULE 2).
 * Geo flag does NOT gate which rule fires — it only affects the modifier
 * via calculateModifier() within the CAUTION regime.
 *
 *   1 — CRISIS HALT:   Brent > $110 OR VIX > 35
 *   2 — CAUTION:       Brent $95–$110 OR VIX 24–35
 *   3 — SOFT CAUTION:  Brent < $100 AND streak < 2 AND VIX < 22
 *   4 — CLEAR:         streak ≥ 2 AND VIX < 24
 *   default            → 2 (CAUTION, −5)
 */
export function determineRule(
  brentPrice: number | null,
  vixValue: number | null,
  brentConsecutiveBelow95Count: number,
): RegimeRule | null {
  if (brentPrice === null || vixValue === null) return null;

  // Rule 1 — Crisis Halt (Brent OR VIX — any geo)
  if (brentPrice > RULE1_BRENT_THRESHOLD || vixValue > RULE1_VIX_THRESHOLD) return 1;

  // Rule 2 — Caution (Brent OR VIX — any geo)
  const cautionMarket =
    (brentPrice >= RULE2_BRENT_LOW && brentPrice <= RULE2_BRENT_HIGH) ||
    (vixValue >= RULE2_VIX_LOW && vixValue <= RULE2_VIX_HIGH);
  if (cautionMarket) return 2;

  // Rule 3 — Soft Caution (Brent AND VIX — any geo)
  const softCautionMarket =
    brentPrice < RULE3_BRENT_THRESHOLD &&
    brentConsecutiveBelow95Count < BRENT_NUM_CLOSES &&
    vixValue < RULE3_VIX_THRESHOLD;
  if (softCautionMarket) return 3;

  // Rule 4 — Clear (both required — any geo)
  const clearMarket =
    brentConsecutiveBelow95Count >= BRENT_NUM_CLOSES && vixValue < RULE4_VIX_CLEAR;
  if (clearMarket) return 4;

  // Default — no specific rule matched; treat as CAUTION
  return 2;
}

/**
 * Return the score modifier for the given regime rule and geo state.
 *
 * Per Section 14.1 KEY RULES:
 * - CLEAR (4):        geo irrelevant → always +5
 * - SOFT CAUTION (3): geo irrelevant → always −3
 * - CRISIS HALT (1):  geo irrelevant → always −10
 * - CAUTION (2):      ESCALATING → −7  (ONLY special case)
 *                     all others → −5
 * - null (default):   → −5 (safe default)
 *
 * Pure function — no I/O.
 */
export function calculateModifier(
  rule: RegimeRule | null,
  geopoliticalState: GeopoliticalState,
): number {
  if (rule === 4) return RULE4_SCORE_DELTA;        // +5 — geo irrelevant
  if (rule === 3) return RULE3_SCORE_DELTA;        // −3 — geo irrelevant
  if (rule === 1) return RULE1_SCORE_DELTA;        // −10 — geo irrelevant
  if (rule === 2) {
    // ONLY special case: CAUTION + ESCALATING geo → −7
    return geopoliticalState === 'ESCALATING' ? RULE2_SCORE_DELTA_ESCALATING : RULE2_SCORE_DELTA;
  }
  return RULE2_SCORE_DELTA; // safe default −5
}

/**
 * Return the effective regime label.
 *
 * Regime is determined by market conditions alone — geo does not change it.
 */
export function deriveEffectiveRegime(
  automaticRegime: AutomaticRegimeLabel,
): EffectiveRegimeLabel {
  return automaticRegime;
}

/**
 * Return a human-readable Brent condition string with zone label.
 * Pure function — no I/O.
 */
export function getBrentLabel(brent: number): string {
  if (brent > RULE1_BRENT_THRESHOLD) return `$${brent.toFixed(2)} — Above $110 (CRISIS trigger)`;
  if (brent >= RULE2_BRENT_LOW && brent <= RULE2_BRENT_HIGH)
    return `$${brent.toFixed(2)} — $95-110 (CAUTION trigger)`;
  if (brent < RULE4_BRENT_CLEAR) return `$${brent.toFixed(2)} — Below $95 (CLEAR zone)`;
  return `$${brent.toFixed(2)}`;
}

/**
 * Return a human-readable VIX condition string with zone label.
 * Pure function — no I/O.
 */
export function getVixLabel(vix: number): string {
  if (vix > RULE1_VIX_THRESHOLD) return `${vix.toFixed(2)} — Above 35 (CRISIS trigger)`;
  if (vix >= RULE2_VIX_LOW && vix <= RULE2_VIX_HIGH)
    return `${vix.toFixed(2)} — 24-35 (CAUTION trigger)`;
  if (vix < RULE3_VIX_THRESHOLD) return `${vix.toFixed(2)} — Below 22 (SOFT CAUTION zone)`;
  if (vix < RULE4_VIX_CLEAR) return `${vix.toFixed(2)} — Below 24 (CLEAR zone)`;
  return `${vix.toFixed(2)}`;
}

/**
 * Return the trigger logic description (OR vs AND) for a regime rule.
 * Pure function — no I/O.
 */
export function getTriggerLogic(rule: RegimeRule | null): string {
  if (rule === 1 || rule === 2) return 'OR — either Brent or VIX triggers';
  return 'AND — both Brent and VIX required';
}

/**
 * Return a human-readable explanation of the modifier applied.
 * Pure function — no I/O.
 */
export function getModifierReason(
  rule: RegimeRule | null,
  geopoliticalState: GeopoliticalState,
): string {
  if (rule === 4) return 'CLEAR → +5 (geo flag ignored)';
  if (rule === 3) return 'SOFT CAUTION → −3 (geo flag ignored)';
  if (rule === 1) return 'CRISIS HALT → −10 (geo flag ignored)';
  if (rule === 2) {
    if (geopoliticalState === 'ESCALATING') return 'CAUTION + Escalating geo → −7';
    const geoLabel = geopoliticalState.replace(/_/g, ' ');
    return `CAUTION + ${geoLabel} → −5`;
  }
  return 'Unknown → −5';
}

/**
 * Return the minimum portfolio cash floor fraction for a regime rule.
 * Pure function — no I/O.
 */
export function getCashFloor(rule: RegimeRule | null): number {
  if (rule === 1) return CASH_FLOOR_RULE1;
  if (rule === 2) return CASH_FLOOR_RULE2;
  if (rule === 3) return CASH_FLOOR_RULE3;
  if (rule === 4) return CASH_FLOOR_RULE4;
  return CASH_FLOOR_RULE2; // default: 20%
}

/**
 * Compute the adjusted score, cash guidance, and output text for a rule.
 *
 * Pure function — no I/O.
 */
export function computeRegimeOutput(
  rule: RegimeRule | null,
  baseScore: number,
  geopoliticalState: GeopoliticalState = 'NONE',
): RegimeOutput {
  let minCashPct: number;
  let maxCashPct: number;
  let outputText: string;

  if (rule === 1) {
    minCashPct = RULE1_MIN_CASH_PCT;
    maxCashPct = RULE1_MAX_CASH_PCT;
    outputText = OUTPUT_RULE1;
  } else if (rule === 2) {
    minCashPct = RULE2_MIN_CASH_PCT;
    maxCashPct = RULE2_MAX_CASH_PCT;
    outputText = geopoliticalState === 'ESCALATING' ? OUTPUT_RULE2_ESCALATING : OUTPUT_RULE2;
  } else if (rule === 3) {
    minCashPct = RULE3_MIN_CASH_PCT;
    maxCashPct = RULE3_MAX_CASH_PCT;
    outputText = OUTPUT_RULE3;
  } else if (rule === 4) {
    minCashPct = RULE4_MIN_CASH_PCT;
    maxCashPct = RULE4_MAX_CASH_PCT;
    outputText = OUTPUT_RULE4;
  } else {
    const adjustedScore = baseScore;
    return { ruleTriggered: null, adjustedScore, minCashPct: 0, maxCashPct: 0, outputText: '' };
  }

  const delta = calculateModifier(rule, geopoliticalState);
  const adjustedScore = Math.max(MIN_SCORE, Math.min(MAX_SCORE, baseScore + delta));

  return { ruleTriggered: rule, adjustedScore, minCashPct, maxCashPct, outputText };
}
