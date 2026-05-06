import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ConvictionActionPanel } from '@/components/frameworks/conviction-action-panel';
import type { ConvictionActionResponse } from '@/lib/schemas/conviction-action';

const useConvictionActionMock = vi.fn();
const useLeapsMock = vi.fn();

vi.mock('@/lib/hooks/use-conviction-action', () => ({
  useConvictionAction: (...args: unknown[]) => useConvictionActionMock(...args),
}));

vi.mock('@/lib/hooks/use-leaps', () => ({
  useLeaps: (...args: unknown[]) => useLeapsMock(...args),
}));

// ---------------------------------------------------------------------------
// Shared mock factories
// ---------------------------------------------------------------------------

function baseResponse(
  overrides: Partial<ConvictionActionResponse> = {},
): ConvictionActionResponse {
  return {
    ticker: 'AAPL',
    final_score: 88,
    tier: 'T1_ELITE',
    tier_label: 'T1 ELITE',
    tier_color: '#39d353',
    score_band_min: 85,
    score_band_max: null,
    size_min_pct: 5.0,
    size_max_pct: 10.0,
    action: 'CORE — LEAPS ELIGIBLE',
    leaps_eligible: true,
    current_weight_pct: 4.2,
    position_size_status: 'IN_RANGE',
    room_to_add_pct: 0.8,
    trim_suggested: false,
    adds_permitted: true,
    adds_blocked_reason: null,
    beta_cap_active: false,
    concentration_cap: false,
    exit_triggered: false,
    exit_cycle_count: 0,
    cluster: 'Tech Mega-Cap',
    cluster_weight_pct: 18.5,
    cluster_status: 'OK',
    rationale: 'Core holding — LEAPS eligible, add on dips',
    ...overrides,
  };
}

function mockData(overrides: Partial<ConvictionActionResponse> = {}) {
  useConvictionActionMock.mockReturnValue({
    data: baseResponse(overrides),
    isLoading: false,
    isError: false,
    error: null,
  });
  useLeapsMock.mockReturnValue({ data: undefined });
}

function mockLoading() {
  useConvictionActionMock.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
    error: null,
  });
  useLeapsMock.mockReturnValue({ data: undefined });
}

function mockError(message = 'Network error') {
  useConvictionActionMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error(message),
  });
  useLeapsMock.mockReturnValue({ data: undefined });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ConvictionActionPanel', () => {
  describe('loading and error states', () => {
    it('renders loading message while fetching', () => {
      mockLoading();
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-loading')).toBeInTheDocument();
    });

    it('renders error message on failure', () => {
      mockError('Conviction fetch failed');
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-error')).toHaveTextContent(
        'Conviction fetch failed',
      );
    });
  });

  describe('tier label', () => {
    it('renders T1 ELITE label for score ≥ 85', () => {
      mockData();
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-tier-label')).toHaveTextContent(
        'T1 ELITE',
      );
    });

    it('renders T1 label for score 80-84', () => {
      mockData({
        tier: 'T1',
        tier_label: 'T1',
        tier_color: '#2dd4bf',
        score_band_min: 80,
        score_band_max: 84,
        final_score: 82,
      });
      render(<ConvictionActionPanel ticker="MSFT" adjustedScore={82} />);
      expect(screen.getByTestId('conviction-tier-label')).toHaveTextContent('T1');
    });

    it('renders BELOW GATE label for score < 50', () => {
      mockData({
        tier: 'BELOW_GATE',
        tier_label: 'BELOW GATE',
        tier_color: '#f85149',
        score_band_min: 0,
        score_band_max: 49,
        final_score: 40,
        size_min_pct: 0,
        size_max_pct: 0,
        leaps_eligible: false,
      });
      render(<ConvictionActionPanel ticker="XYZ" adjustedScore={40} />);
      expect(screen.getByTestId('conviction-tier-label')).toHaveTextContent('BELOW GATE');
    });
  });

  describe('score band row', () => {
    it('shows "85+" for T1_ELITE (no ceiling)', () => {
      mockData({ score_band_min: 85, score_band_max: null });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-score-band')).toHaveTextContent('85+');
    });

    it('shows "80–84" for T1', () => {
      mockData({
        tier: 'T1',
        tier_label: 'T1',
        score_band_min: 80,
        score_band_max: 84,
      });
      render(<ConvictionActionPanel ticker="MSFT" adjustedScore={80} />);
      expect(screen.getByTestId('conviction-score-band')).toHaveTextContent('80–84');
    });
  });

  describe('position details panel', () => {
    it('shows current weight', () => {
      mockData({ current_weight_pct: 4.2 });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-position-panel')).toHaveTextContent('4.20%');
    });

    it('shows adds permitted as YES when allowed', () => {
      mockData({ adds_permitted: true });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-adds-permitted')).toHaveTextContent('YES');
    });

    it('shows adds permitted as NO when blocked', () => {
      mockData({
        adds_permitted: false,
        adds_blocked_reason: 'Beta cap (F13) blocking adds',
      });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-adds-permitted')).toHaveTextContent('NO');
    });

    it('shows blocked reason when adds_permitted is false', () => {
      mockData({
        adds_permitted: false,
        adds_blocked_reason: 'Beta cap (F13) blocking adds',
      });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-blocked-reason')).toHaveTextContent(
        'Beta cap (F13) blocking adds',
      );
    });

    it('does not show blocked reason when adds_permitted is true', () => {
      mockData({ adds_permitted: true, adds_blocked_reason: null });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.queryByTestId('conviction-blocked-reason')).not.toBeInTheDocument();
    });
  });

  describe('consensus panel', () => {
    it('does NOT show consensus panel (consensus removed in v7.3.5)', () => {
      mockData();
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.queryByTestId('conviction-consensus-panel')).not.toBeInTheDocument();
    });
  });

  describe('LEAPS chip', () => {
    it('shows LEAPS chip when leaps_eligible is true', () => {
      mockData({ leaps_eligible: true });
      useLeapsMock.mockReturnValue({ data: { leaps_eligible: true } });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-leaps-chip')).toBeInTheDocument();
      expect(screen.getByTestId('conviction-leaps-chip')).toHaveTextContent('LEAPS ELIGIBLE');
    });

    it('does NOT show LEAPS chip when tier is not T1_ELITE', () => {
      mockData({ tier: 'T1', leaps_eligible: false });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={82} />);
      expect(screen.queryByTestId('conviction-leaps-chip')).not.toBeInTheDocument();
    });
  });

  describe('exit counter', () => {
    it('shows exit counter for BELOW_GATE tier', () => {
      mockData({
        tier: 'BELOW_GATE',
        tier_label: 'BELOW GATE',
        tier_color: '#f85149',
        score_band_min: 0,
        score_band_max: 49,
        leaps_eligible: false,
        exit_cycle_count: 1,
        exit_triggered: false,
      });
      render(<ConvictionActionPanel ticker="XYZ" adjustedScore={40} />);
      expect(screen.getByTestId('conviction-exit-counter')).toBeInTheDocument();
      expect(screen.getByTestId('conviction-exit-counter')).toHaveTextContent('1 / 2');
    });

    it('does NOT show exit counter for non-BELOW_GATE tiers', () => {
      mockData({ tier: 'T1_ELITE' });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.queryByTestId('conviction-exit-counter')).not.toBeInTheDocument();
    });

    it('shows exit alert when exit_triggered is true', () => {
      mockData({
        tier: 'BELOW_GATE',
        tier_label: 'BELOW GATE',
        tier_color: '#f85149',
        score_band_min: 0,
        score_band_max: 49,
        leaps_eligible: false,
        exit_cycle_count: 2,
        exit_triggered: true,
      });
      render(<ConvictionActionPanel ticker="XYZ" adjustedScore={40} />);
      expect(screen.getByTestId('conviction-exit-alert')).toBeInTheDocument();
    });
  });

  describe('cluster panel', () => {
    it('always shows cluster panel', () => {
      mockData({ cluster: 'Tech Mega-Cap', cluster_weight_pct: 18.5, cluster_status: 'OK' });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-cluster-panel')).toBeInTheDocument();
      expect(screen.getByTestId('conviction-cluster-panel')).toHaveTextContent('Tech Mega-Cap');
    });
  });

  describe('bottom message', () => {
    it('shows tier default message when adds are permitted (T2)', () => {
      mockData({ tier: 'T2', adds_permitted: true, adds_blocked_reason: null });
      render(<ConvictionActionPanel ticker="NVDA" adjustedScore={72} />);
      expect(screen.getByTestId('conviction-rationale')).toHaveTextContent(
        'Small satellites only',
      );
    });

    it('shows blocked message when adds are not permitted', () => {
      mockData({ adds_permitted: false, adds_blocked_reason: 'Beta cap (F13) blocking adds' });
      render(<ConvictionActionPanel ticker="MU" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-rationale')).toHaveTextContent(
        'Adds blocked — Beta cap (F13) blocking adds',
      );
    });

    it('shows T1_ELITE message when adds are permitted', () => {
      mockData({ tier: 'T1_ELITE', adds_permitted: true, adds_blocked_reason: null });
      render(<ConvictionActionPanel ticker="AAPL" adjustedScore={88} />);
      expect(screen.getByTestId('conviction-rationale')).toHaveTextContent(
        'Core holding — LEAPS eligible, add on dips',
      );
    });
  });
});
