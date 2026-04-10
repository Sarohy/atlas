import { describe, expect, it } from 'vitest';
import {
  determineRule,
  computeRegimeOutput,
  RULE1_BRENT_THRESHOLD,
  RULE1_VIX_THRESHOLD,
  RULE2_BRENT_LOW,
  RULE2_BRENT_HIGH,
  RULE2_VIX_LOW,
  RULE2_VIX_HIGH,
  RULE3_VIX_CLEAR,
} from '@/lib/utils/regime-rules';

// ---------------------------------------------------------------------------
// determineRule
// ---------------------------------------------------------------------------

describe('determineRule', () => {
  describe('Rule 1 — Crisis', () => {
    it('triggers on active_war regardless of market data', () => {
      expect(determineRule(true, 80, 20, false)).toBe(1);
    });

    it('triggers when brent > 110', () => {
      expect(determineRule(false, RULE1_BRENT_THRESHOLD + 0.01, 20, false)).toBe(1);
    });

    it('does NOT trigger when brent is exactly 110', () => {
      expect(determineRule(false, RULE1_BRENT_THRESHOLD, 20, false)).not.toBe(1);
    });

    it('triggers when vix > 35', () => {
      expect(determineRule(false, 80, RULE1_VIX_THRESHOLD + 0.1, false)).toBe(1);
    });

    it('does NOT trigger when vix is exactly 35', () => {
      expect(determineRule(false, 80, RULE1_VIX_THRESHOLD, false)).not.toBe(1);
    });

    it('takes priority over rule 2 conditions', () => {
      expect(determineRule(true, 100, 28, false)).toBe(1);
    });
  });

  describe('Rule 2 — Caution', () => {
    it('triggers when brent in [95,110] AND vix in [24,35]', () => {
      expect(determineRule(false, 100, 28, false)).toBe(2);
    });

    it('triggers at lower brent boundary (95) and lower vix boundary (24)', () => {
      expect(determineRule(false, RULE2_BRENT_LOW, RULE2_VIX_LOW, false)).toBe(2);
    });

    it('triggers at upper brent boundary (110) and upper vix boundary (35)', () => {
      expect(determineRule(false, RULE2_BRENT_HIGH, RULE2_VIX_HIGH, false)).toBe(2);
    });

    it('does NOT trigger with only brent in range', () => {
      expect(determineRule(false, 100, 23, false)).toBeNull();
    });

    it('does NOT trigger with only vix in range', () => {
      expect(determineRule(false, 94, 28, false)).toBeNull();
    });
  });

  describe('Rule 3 — Clear', () => {
    it('triggers when brent below 95 for 2 consecutive closes AND vix < 24', () => {
      expect(determineRule(false, 90, 22, true)).toBe(3);
    });

    it('does NOT trigger without two consecutive closes', () => {
      expect(determineRule(false, 90, 22, false)).toBeNull();
    });

    it('does NOT trigger when vix is at or above 24', () => {
      expect(determineRule(false, 90, RULE3_VIX_CLEAR, true)).toBeNull();
    });
  });

  describe('No rule', () => {
    it('returns null in a normal market', () => {
      expect(determineRule(false, 85, 18, false)).toBeNull();
    });
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

  it('active war with base 57 → adjusted 47', () => {
    // Mirrors backend regression test
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
