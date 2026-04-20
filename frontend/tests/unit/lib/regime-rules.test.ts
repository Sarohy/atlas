import { describe, expect, it } from 'vitest';
import {
  computeRegimeOutput,
  deriveEffectiveRegime,
  determineRule,
  RULE1_BRENT_THRESHOLD,
  RULE1_VIX_THRESHOLD,
  RULE2_BRENT_LOW,
  RULE2_BRENT_HIGH,
} from '@/lib/utils/regime-rules';

// ---------------------------------------------------------------------------
// determineRule
// ---------------------------------------------------------------------------

describe('determineRule', () => {
  describe('Rule 1 — Crisis', () => {
    it('triggers when brent > 110', () => {
      expect(determineRule(RULE1_BRENT_THRESHOLD + 0.01, 20, 0)).toBe(1);
    });

    it('does NOT trigger when brent is exactly 110', () => {
      expect(determineRule(RULE1_BRENT_THRESHOLD, 20, 0)).not.toBe(1);
    });

    it('triggers when vix > 35', () => {
      expect(determineRule(80, RULE1_VIX_THRESHOLD + 0.1, 0)).toBe(1);
    });

    it('does NOT trigger when vix is exactly 35', () => {
      expect(determineRule(80, RULE1_VIX_THRESHOLD, 0)).not.toBe(1);
    });
  });

  describe('Rule 2 — Caution', () => {
    it('triggers when brent in [95,110]', () => {
      expect(determineRule(100, 28, 0)).toBe(2);
    });

    it('triggers at lower brent boundary (95)', () => {
      expect(determineRule(RULE2_BRENT_LOW, 18, 0)).toBe(2);
    });

    it('triggers at upper brent boundary (110)', () => {
      expect(determineRule(RULE2_BRENT_HIGH, 35, 0)).toBe(2);
    });

    it('triggers when brent is below 95 but the clear streak is not met', () => {
      expect(determineRule(90, 20, 1)).toBe(2);
    });

    it('does NOT trigger with only vix in range', () => {
      expect(determineRule(94, 28, 0)).toBeNull();
    });
  });

  describe('Rule 3 — Clear', () => {
    it('triggers when brent below 95 for 2 consecutive closes AND vix < 24', () => {
      expect(determineRule(90, 22, 2)).toBe(3);
    });

    it('does NOT trigger without two consecutive closes', () => {
      expect(determineRule(90, 22, 1)).toBe(2);
    });
  });

  describe('No rule', () => {
    it('returns null in a normal market', () => {
      expect(determineRule(85, 25, 0)).toBeNull();
    });
  });
});

describe('deriveEffectiveRegime', () => {
  it('preserves the automatic regime when the geopolitical gate is NONE', () => {
    expect(deriveEffectiveRegime('CLEAR', 'NONE')).toBe('CLEAR');
  });

  it('returns soft caution when clear is gated by active geopolitics', () => {
    expect(deriveEffectiveRegime('CLEAR', 'ACTIVE')).toBe('SOFT CAUTION');
  });

  it('returns soft caution when normal is gated by de-escalating geopolitics', () => {
    expect(deriveEffectiveRegime('NORMAL', 'DE_ESCALATING')).toBe('SOFT CAUTION');
  });

  it('does not downgrade an existing caution regime', () => {
    expect(deriveEffectiveRegime('CAUTION', 'ACTIVE')).toBe('CAUTION');
  });
});

// ---------------------------------------------------------------------------
// computeRegimeOutput
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

  it('rule 2 deducts 5 points', () => {
    expect(computeRegimeOutput(2, 75).adjustedScore).toBe(70);
  });

  it('rule 2 sets min/max cash pct to 25%/35%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(2, 75);
    expect(minCashPct).toBeCloseTo(0.25);
    expect(maxCashPct).toBeCloseTo(0.35);
  });

  it('rule 3 adds 5 points', () => {
    expect(computeRegimeOutput(3, 75).adjustedScore).toBe(80);
  });

  it('rule 3 clamps adjusted score at 100', () => {
    expect(computeRegimeOutput(3, 98).adjustedScore).toBe(100);
  });

  it('rule 3 sets min/max cash pct to 10%/12%', () => {
    const { minCashPct, maxCashPct } = computeRegimeOutput(3, 75);
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
    expect(out.minCashPct).toBeCloseTo(0.35);
    expect(out.maxCashPct).toBeCloseTo(0.4);
  });

  it('output text is non-empty for rule 1', () => {
    expect(computeRegimeOutput(1, 75).outputText).not.toBe('');
  });

  it('output text is empty when no rule fires', () => {
    expect(computeRegimeOutput(null, 75).outputText).toBe('');
  });
});
