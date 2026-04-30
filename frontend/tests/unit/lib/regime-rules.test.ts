import { describe, expect, it } from 'vitest';
import {
  calculateModifier,
  computeRegimeOutput,
  deriveEffectiveRegime,
  determineRule,
  getBrentLabel,
  getCashFloor,
  getModifierReason,
  getTriggerLogic,
  getVixLabel,
  RULE1_BRENT_THRESHOLD,
  RULE1_VIX_THRESHOLD,
  RULE2_BRENT_HIGH,
  RULE2_BRENT_LOW,
  RULE3_BRENT_THRESHOLD,
  RULE3_VIX_THRESHOLD,
  RULE4_BRENT_CLEAR,
  RULE4_VIX_CLEAR,
} from '@/lib/utils/regime-rules';

// ---------------------------------------------------------------------------
// determineRule — market conditions only (Section 14.1 KEY RULE 2)
// ---------------------------------------------------------------------------

describe('determineRule', () => {
  describe('Rule 1 — Crisis Halt (Brent OR VIX, any geo)', () => {
    it('triggers when brent > 110', () => {
      expect(determineRule(RULE1_BRENT_THRESHOLD + 0.01, 20, 0)).toBe(1);
    });

    it('does NOT trigger when brent is exactly 110', () => {
      expect(determineRule(RULE1_BRENT_THRESHOLD, 20, 0)).not.toBe(1);
    });

    it('triggers when vix > 35', () => {
      expect(determineRule(80, RULE1_VIX_THRESHOLD + 0.1, 0)).toBe(1);
    });

    it('triggers regardless of geo — ACTIVE_RISK', () => {
      expect(determineRule(115, 40, 0)).toBe(1);
    });

    it('triggers regardless of geo — NONE', () => {
      expect(determineRule(115, 40, 0)).toBe(1);
    });

    it('does NOT trigger when market is calm', () => {
      expect(determineRule(80, 20, 0)).not.toBe(1);
    });
  });

  describe('Rule 2 — Caution (Brent OR VIX, any geo)', () => {
    it('triggers when brent in [95,110]', () => {
      expect(determineRule(100, 20, 0)).toBe(2);
    });

    it('triggers when vix in [24,35]', () => {
      expect(determineRule(80, 28, 2)).toBe(2);
    });

    it('triggers at lower brent boundary (95)', () => {
      expect(determineRule(RULE2_BRENT_LOW, 18, 0)).toBe(2);
    });

    it('triggers at upper brent boundary (110)', () => {
      expect(determineRule(RULE2_BRENT_HIGH, 20, 0)).toBe(2);
    });

    it('triggers regardless of geo when market conditions fire', () => {
      expect(determineRule(100, 28, 0)).toBe(2);
    });
  });

  describe('Rule 3 — Soft Caution (Brent AND VIX AND streak, any geo)', () => {
    it('triggers when brent < 100, streak < 2, vix < 22', () => {
      expect(determineRule(90, 20, 1)).toBe(3);
    });

    it('triggers regardless of geo', () => {
      expect(determineRule(92, 20, 1)).toBe(3);
    });

    it('does NOT trigger when brent is at threshold (100)', () => {
      expect(determineRule(RULE3_BRENT_THRESHOLD, 20, 1)).not.toBe(3);
    });

    it('does NOT trigger when vix is at threshold (22)', () => {
      expect(determineRule(90, RULE3_VIX_THRESHOLD, 1)).not.toBe(3);
    });

    it('does NOT trigger when streak is 2 or more', () => {
      expect(determineRule(90, 20, 2)).not.toBe(3);
    });
  });

  describe('Rule 4 — Clear (streak AND VIX, any geo)', () => {
    it('triggers when streak >= 2 and vix < 24', () => {
      expect(determineRule(RULE4_BRENT_CLEAR - 1, 22, 2)).toBe(4);
    });

    it('triggers regardless of geo', () => {
      expect(determineRule(90, 22, 2)).toBe(4);
    });

    it('does NOT trigger with single brent close', () => {
      expect(determineRule(90, 22, 1)).not.toBe(4);
    });

    it('does NOT trigger when vix is at or above threshold (24)', () => {
      expect(determineRule(90, RULE4_VIX_CLEAR, 2)).not.toBe(4);
    });
  });

  describe('Default fallback', () => {
    it('returns null when brent is null', () => {
      expect(determineRule(null, 20, 0)).toBeNull();
    });

    it('returns null when vix is null', () => {
      expect(determineRule(85, null, 0)).toBeNull();
    });
  });
});

// ---------------------------------------------------------------------------
// calculateModifier — geo only matters for CAUTION + ESCALATING
// ---------------------------------------------------------------------------

describe('calculateModifier', () => {
  it('CRISIS HALT (1) → −10 regardless of geo', () => {
    expect(calculateModifier(1, 'ESCALATING')).toBe(-10);
    expect(calculateModifier(1, 'NONE')).toBe(-10);
    expect(calculateModifier(1, 'RESOLVED')).toBe(-10);
  });

  it('SOFT CAUTION (3) → −3 regardless of geo', () => {
    expect(calculateModifier(3, 'ESCALATING')).toBe(-3);
    expect(calculateModifier(3, 'NONE')).toBe(-3);
  });

  it('CLEAR (4) → +5 regardless of geo', () => {
    expect(calculateModifier(4, 'RESOLVED')).toBe(5);
    expect(calculateModifier(4, 'ESCALATING')).toBe(5);
    expect(calculateModifier(4, 'NONE')).toBe(5);
  });

  it('CAUTION (2) + ESCALATING → −7 (the ONLY special case)', () => {
    expect(calculateModifier(2, 'ESCALATING')).toBe(-7);
  });

  it('CAUTION (2) + ACTIVE_RISK → −5', () => {
    expect(calculateModifier(2, 'ACTIVE_RISK')).toBe(-5);
  });

  it('CAUTION (2) + DE_ESCALATING → −5', () => {
    expect(calculateModifier(2, 'DE_ESCALATING')).toBe(-5);
  });

  it('CAUTION (2) + RESOLVED → −5', () => {
    expect(calculateModifier(2, 'RESOLVED')).toBe(-5);
  });

  it('CAUTION (2) + NONE → −5', () => {
    expect(calculateModifier(2, 'NONE')).toBe(-5);
  });

  it('null rule → safe default −5', () => {
    expect(calculateModifier(null, 'NONE')).toBe(-5);
  });
});

// ---------------------------------------------------------------------------
// getBrentLabel
// ---------------------------------------------------------------------------

describe('getBrentLabel', () => {
  it('above $110 shows CRISIS trigger', () => {
    expect(getBrentLabel(112)).toContain('CRISIS trigger');
  });

  it('in $95-$110 range shows CAUTION trigger', () => {
    expect(getBrentLabel(100)).toContain('CAUTION trigger');
  });

  it('below $95 shows CLEAR zone', () => {
    expect(getBrentLabel(90)).toContain('CLEAR zone');
  });

  it('includes formatted price', () => {
    expect(getBrentLabel(97.5)).toContain('$97.50');
  });
});

// ---------------------------------------------------------------------------
// getVixLabel
// ---------------------------------------------------------------------------

describe('getVixLabel', () => {
  it('above 35 shows CRISIS trigger', () => {
    expect(getVixLabel(36)).toContain('CRISIS trigger');
  });

  it('in 24-35 range shows CAUTION trigger', () => {
    expect(getVixLabel(28)).toContain('CAUTION trigger');
  });

  it('below 22 shows SOFT CAUTION zone', () => {
    expect(getVixLabel(18)).toContain('SOFT CAUTION zone');
  });

  it('22-24 range shows CLEAR zone', () => {
    expect(getVixLabel(23)).toContain('CLEAR zone');
  });
});

// ---------------------------------------------------------------------------
// getTriggerLogic
// ---------------------------------------------------------------------------

describe('getTriggerLogic', () => {
  it('rule 1 uses OR logic', () => {
    expect(getTriggerLogic(1)).toContain('OR');
  });

  it('rule 2 uses OR logic', () => {
    expect(getTriggerLogic(2)).toContain('OR');
  });

  it('rule 3 uses AND logic', () => {
    expect(getTriggerLogic(3)).toContain('AND');
  });

  it('rule 4 uses AND logic', () => {
    expect(getTriggerLogic(4)).toContain('AND');
  });

  it('null rule uses AND logic (default)', () => {
    expect(getTriggerLogic(null)).toContain('AND');
  });
});

// ---------------------------------------------------------------------------
// getModifierReason
// ---------------------------------------------------------------------------

describe('getModifierReason', () => {
  it('CLEAR (4) returns geo-ignored message', () => {
    expect(getModifierReason(4, 'ESCALATING')).toContain('geo flag ignored');
    expect(getModifierReason(4, 'ESCALATING')).toContain('+5');
  });

  it('SOFT CAUTION (3) returns geo-ignored message', () => {
    expect(getModifierReason(3, 'NONE')).toContain('geo flag ignored');
    expect(getModifierReason(3, 'NONE')).toContain('−3');
  });

  it('CRISIS HALT (1) returns geo-ignored message', () => {
    expect(getModifierReason(1, 'ACTIVE_RISK')).toContain('geo flag ignored');
    expect(getModifierReason(1, 'ACTIVE_RISK')).toContain('−10');
  });

  it('CAUTION (2) + ESCALATING returns the special case −7 message', () => {
    expect(getModifierReason(2, 'ESCALATING')).toContain('−7');
    expect(getModifierReason(2, 'ESCALATING')).toContain('Escalating');
  });

  it('CAUTION (2) + ACTIVE_RISK returns standard −5', () => {
    expect(getModifierReason(2, 'ACTIVE_RISK')).toContain('−5');
  });
});

// ---------------------------------------------------------------------------
// getCashFloor
// ---------------------------------------------------------------------------

describe('getCashFloor', () => {
  it('rule 1 (CRISIS HALT) → 30% floor', () => {
    expect(getCashFloor(1)).toBeCloseTo(0.30);
  });

  it('rule 2 (CAUTION) → 20% floor', () => {
    expect(getCashFloor(2)).toBeCloseTo(0.20);
  });

  it('rule 3 (SOFT CAUTION) → 15% floor', () => {
    expect(getCashFloor(3)).toBeCloseTo(0.15);
  });

  it('rule 4 (CLEAR) → 8% floor', () => {
    expect(getCashFloor(4)).toBeCloseTo(0.08);
  });

  it('null → 20% floor (safe default)', () => {
    expect(getCashFloor(null)).toBeCloseTo(0.20);
  });
});

// ---------------------------------------------------------------------------
// deriveEffectiveRegime
// ---------------------------------------------------------------------------

describe('deriveEffectiveRegime', () => {
  it('returns the automatic regime unchanged', () => {
    expect(deriveEffectiveRegime('CLEAR')).toBe('CLEAR');
    expect(deriveEffectiveRegime('CAUTION')).toBe('CAUTION');
    expect(deriveEffectiveRegime('SOFT CAUTION')).toBe('SOFT CAUTION');
    expect(deriveEffectiveRegime('CRISIS HALT')).toBe('CRISIS HALT');
  });
});

// ---------------------------------------------------------------------------
// computeRegimeOutput — uses calculateModifier internally
// ---------------------------------------------------------------------------

describe('computeRegimeOutput', () => {
  it('rule 1 deducts 10 points', () => {
    expect(computeRegimeOutput(1, 75).adjustedScore).toBe(65);
  });

  it('rule 1 clamps adjusted score at 0', () => {
    expect(computeRegimeOutput(1, 8).adjustedScore).toBe(0);
  });

  it('rule 1 sets min/max cash pct to 35%/40%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(1, 75);
    expect(minCashPct).toBeCloseTo(0.35);
    expect(maxCashPct).toBeCloseTo(0.4);
  });

  it('rule 2 + NONE deducts 5 points (standard)', () => {
    expect(computeRegimeOutput(2, 75, 'NONE').adjustedScore).toBe(70);
  });

  it('rule 2 + ESCALATING deducts 7 points (special case)', () => {
    expect(computeRegimeOutput(2, 75, 'ESCALATING').adjustedScore).toBe(68);
  });

  it('rule 2 ESCALATING output text includes GEO PENALTY ACTIVE', () => {
    expect(computeRegimeOutput(2, 75, 'ESCALATING').outputText).toContain('GEO PENALTY ACTIVE');
  });

  it('rule 2 non-ESCALATING output text does NOT include GEO PENALTY ACTIVE', () => {
    expect(computeRegimeOutput(2, 75, 'ACTIVE_RISK').outputText).not.toContain('GEO PENALTY ACTIVE');
  });

  it('rule 2 sets min/max cash pct to 25%/35%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(2, 75);
    expect(minCashPct).toBeCloseTo(0.25);
    expect(maxCashPct).toBeCloseTo(0.35);
  });

  it('rule 3 deducts 3 points', () => {
    expect(computeRegimeOutput(3, 75).adjustedScore).toBe(72);
  });

  it('rule 3 sets min/max cash pct to 15%/25%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(3, 75);
    expect(minCashPct).toBeCloseTo(0.15);
    expect(maxCashPct).toBeCloseTo(0.25);
  });

  it('rule 4 adds 5 points', () => {
    expect(computeRegimeOutput(4, 75).adjustedScore).toBe(80);
  });

  it('rule 4 clamps adjusted score at 100', () => {
    expect(computeRegimeOutput(4, 98).adjustedScore).toBe(100);
  });

  it('rule 4 sets min/max cash pct to 10%/12%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(4, 75);
    expect(minCashPct).toBeCloseTo(0.1);
    expect(maxCashPct).toBeCloseTo(0.12);
  });

  it('no rule preserves score and returns zero cash pcts', () => {
    const out = computeRegimeOutput(null, 72);
    expect(out.adjustedScore).toBe(72);
    expect(out.minCashPct).toBe(0);
    expect(out.maxCashPct).toBe(0);
  });

  it('rule 1 with base 57 → adjusted 47', () => {
    const out = computeRegimeOutput(1, 57);
    expect(out.adjustedScore).toBe(47);
  });

  it('output text is non-empty for rule 1', () => {
    expect(computeRegimeOutput(1, 75).outputText).not.toBe('');
  });

  it('output text is non-empty for rule 3', () => {
    expect(computeRegimeOutput(3, 75).outputText).not.toBe('');
  });

  it('output text is empty when no rule fires', () => {
    expect(computeRegimeOutput(null, 75).outputText).toBe('');
  });
});


