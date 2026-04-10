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
export const RULE2_MIN_CASH_PCT = 0.25;
export const RULE2_MAX_CASH_PCT = 0.35;

// Rule 3 — Clear thresholds
export const RULE3_BRENT_CLEAR = 95.0;
export const RULE3_VIX_CLEAR = 24.0;
export const RULE3_SCORE_DELTA = 5;
export const RULE3_MIN_CASH_PCT = 0.1;
export const RULE3_MAX_CASH_PCT = 0.12;

// Score bounds
const MIN_SCORE = 0;
const MAX_SCORE = 100;

// Output text — matches spec verbatim
const OUTPUT_RULE1 = 'must stay in cash\ncannot be touched\nfor any trade';
const OUTPUT_RULE2 = 'must stay in cash';
const OUTPUT_RULE3 = 'only this stays in cash\neverything else\ncan be deployed';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RegimeRule = 1 | 2 | 3;

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
 * Rules are evaluated in priority order:
 *   1 (Crisis)  — activeWar OR brent > 110 OR vix > 35
 *   2 (Caution) — brent ∈ [95, 110] AND vix ∈ [24, 35]
 *   3 (Clear)   — brentConsecutiveBelow95 AND vix < 24
 *
 * Null market data with no active war → no rule fires.
 */
export function determineRule(
  activeWar: boolean,
  brentPrice: number | null,
  vixValue: number | null,
  brentConsecutiveBelow95: boolean,
): RegimeRule | null {
  if (activeWar) return 1;
  if (brentPrice === null || vixValue === null) return null;

  if (brentPrice > RULE1_BRENT_THRESHOLD || vixValue > RULE1_VIX_THRESHOLD) return 1;

  const brentInCaution = brentPrice >= RULE2_BRENT_LOW && brentPrice <= RULE2_BRENT_HIGH;
  const vixInCaution = vixValue >= RULE2_VIX_LOW && vixValue <= RULE2_VIX_HIGH;
  if (brentInCaution && vixInCaution) return 2;

  if (brentConsecutiveBelow95 && vixValue < RULE3_VIX_CLEAR) return 3;

  return null;
}

/**
 * Compute the adjusted score, cash guidance, and output text for a rule.
 *
 * Pure function — no I/O.
 */
export function computeRegimeOutput(rule: RegimeRule | null, baseScore: number): RegimeOutput {
  let delta: number;
  let minCashPct: number;
  let maxCashPct: number;
  let outputText: string;

  if (rule === 1) {
    delta = RULE1_SCORE_DELTA;
    minCashPct = RULE1_MIN_CASH_PCT;
    maxCashPct = RULE1_MAX_CASH_PCT;
    outputText = OUTPUT_RULE1;
  } else if (rule === 2) {
    delta = RULE2_SCORE_DELTA;
    minCashPct = RULE2_MIN_CASH_PCT;
    maxCashPct = RULE2_MAX_CASH_PCT;
    outputText = OUTPUT_RULE2;
  } else if (rule === 3) {
    delta = RULE3_SCORE_DELTA;
    minCashPct = RULE3_MIN_CASH_PCT;
    maxCashPct = RULE3_MAX_CASH_PCT;
    outputText = OUTPUT_RULE3;
  } else {
    delta = 0;
    minCashPct = 0;
    maxCashPct = 0;
    outputText = '';
  }

  const adjustedScore = Math.max(MIN_SCORE, Math.min(MAX_SCORE, baseScore + delta));

  return { ruleTriggered: rule, adjustedScore, minCashPct, maxCashPct, outputText };
}
