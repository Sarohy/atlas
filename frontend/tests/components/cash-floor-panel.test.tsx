import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CashFloorPanel } from '@/components/frameworks/cash-floor-panel';
import type { Framework5Response } from '@/lib/schemas/cash-floor';

const useFramework5Mock = vi.fn();

vi.mock('@/lib/hooks/use-cash-floor', () => ({
  useFramework5: (...args: unknown[]) => useFramework5Mock(...args),
}));

// ---------------------------------------------------------------------------
// Shared mock factories
// ---------------------------------------------------------------------------

function baseResponse(overrides: Partial<Framework5Response> = {}): Framework5Response {
  return {
    regime: 'CAUTION',
    brent_price: 102.5,
    vix_value: 27.8,
    floor_pct: 0.20,
    floor_pct_display: '20%',
    floor_amount: 400_000,
    total_nav: 2_000_000,
    total_cash: 800_000,
    cash_pct: 0.40,
    buffer: 400_000,
    buffer_pct: 0.20,
    available_above_floor: 400_000,
    shortfall: 0,
    is_below_floor: false,
    floor_status: 'HEALTHY',
    warning_level: 'NONE',
    warning_message: null,
    deployment_permitted: true,
    transition_active: false,
    transition_floor_pct: null,
    days_until_settled: null,
    clear_transition_date: null,
    effective_beta: 1.55,
    target_beta: 1.75,
    beta_status: 'NORMAL',
    floor_breach_available: true,
    breach_count_this_quarter: 0,
    rationale: 'CAUTION — Deploy T1 only. 20% minimum floor.',
    ...overrides,
  };
}

function mockHealthy(overrides: Partial<Framework5Response> = {}) {
  useFramework5Mock.mockReturnValue({
    data: baseResponse(overrides),
    isLoading: false,
    isError: false,
    error: null,
  });
}

function mockBelowFloor() {
  useFramework5Mock.mockReturnValue({
    data: baseResponse({
      total_cash: 100_000,
      cash_pct: 0.05,
      buffer: 0,
      buffer_pct: 0,
      available_above_floor: 0,
      shortfall: 300_000,
      is_below_floor: true,
      floor_status: 'BELOW_FLOOR',
      warning_level: 'CRITICAL',
      warning_message:
        'CRITICAL — BELOW FLOOR. Shortfall: $300,000.00. No deployment permitted.',
      deployment_permitted: false,
      rationale: 'Below floor — no deployment permitted until cash replenished above minimum floor.',
    }),
    isLoading: false,
    isError: false,
    error: null,
  });
}

function mockClearTransition() {
  useFramework5Mock.mockReturnValue({
    data: baseResponse({
      regime: 'CLEAR',
      floor_pct: 0.10,
      floor_pct_display: '10% (transition — drops to 8% in 7 days)',
      floor_amount: 200_000,
      transition_active: true,
      transition_floor_pct: 0.10,
      days_until_settled: 7,
      clear_transition_date: '2026-04-16',
      rationale: 'CLEAR (transition) — 10% floor. Drops to 8% in 7 days.',
    }),
    isLoading: false,
    isError: false,
    error: null,
  });
}

function mockCriticalZero() {
  useFramework5Mock.mockReturnValue({
    data: baseResponse({
      total_cash: 0,
      cash_pct: 0,
      buffer: 0,
      buffer_pct: 0,
      available_above_floor: 0,
      shortfall: 400_000,
      is_below_floor: true,
      floor_status: 'CRITICAL_ZERO',
      warning_level: 'CRITICAL',
      warning_message: 'CRITICAL — ZERO CASH. Immediate replenishment required.',
      deployment_permitted: false,
    }),
    isLoading: false,
    isError: false,
    error: null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CashFloorPanel', () => {
  // ── Header / loading / error ────────────────────────────────────────────
  it('renders the Framework 5 panel header', () => {
    useFramework5Mock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });
    render(<CashFloorPanel />);
    expect(screen.getByText('Framework 5')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    useFramework5Mock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-loading')).toBeInTheDocument();
  });

  it('shows error state on failure', () => {
    useFramework5Mock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    });
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-error')).toHaveTextContent('Network error');
  });

  // ── Market snapshot ─────────────────────────────────────────────────────
  it('displays Brent price', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-brent')).toHaveTextContent('$102.50');
  });

  it('displays VIX value', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-vix')).toHaveTextContent('27.80');
  });

  // ── Floor details ───────────────────────────────────────────────────────
  it('displays floor percentage display string', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-range-value')).toHaveTextContent('20%');
  });

  it('displays total portfolio NAV', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-position-value')).toHaveTextContent('$2,000,000.00');
  });

  it('displays floor amount in USD', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-min-value')).toHaveTextContent('$400,000.00');
  });

  it('displays cash held row', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-cash-held-row')).toBeInTheDocument();
    expect(screen.getByTestId('cash-floor-cash-held-value')).toHaveTextContent('$800,000.00');
  });

  it('displays available above floor', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-available-value')).toHaveTextContent('$400,000.00');
  });

  // ── Status chip ─────────────────────────────────────────────────────────
  it('shows HEALTHY status chip when above floor', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-status-chip')).toHaveTextContent('HEALTHY');
  });

  it('shows BELOW FLOOR chip when cash is below minimum', () => {
    mockBelowFloor();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-status-chip')).toHaveTextContent(/BELOW/i);
  });

  // ── Warning box ─────────────────────────────────────────────────────────
  it('shows warning box when warning_level is CRITICAL', () => {
    mockBelowFloor();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-warning-box')).toBeInTheDocument();
  });

  it('does not show warning box when warning_level is NONE', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.queryByTestId('cash-floor-warning-box')).not.toBeInTheDocument();
  });

  // ── Rationale ───────────────────────────────────────────────────────────
  it('shows the rationale message', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-rationale')).toHaveTextContent('Deploy T1 only');
  });

  it('shows no-deployment rationale when below floor', () => {
    mockBelowFloor();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-rationale')).toHaveTextContent(
      /no deployment permitted/i,
    );
  });

  // ── CLEAR transition ────────────────────────────────────────────────────
  it('shows transition countdown when CLEAR transition is active', () => {
    mockClearTransition();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-range-value')).toHaveTextContent(/transition/i);
  });

  // ── Amber warning ───────────────────────────────────────────────────────
  it('shows amber warning box when warning_level is AMBER', () => {
    mockHealthy({
      floor_status: 'AT_FLOOR',
      warning_level: 'AMBER',
      warning_message: 'At floor — no buffer available.',
      deployment_permitted: false,
      buffer: 0,
      available_above_floor: 0,
    });
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-warning-box')).toBeInTheDocument();
  });

  // ── Status chip labels ───────────────────────────────────────────────────
  it('shows "CRITICAL — ZERO CASH" label for CRITICAL_ZERO status', () => {
    mockCriticalZero();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-status-chip')).toHaveTextContent('CRITICAL — ZERO CASH');
  });

  it('shows "CRITICAL — BELOW FLOOR" label for BELOW_FLOOR status', () => {
    mockBelowFloor();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-status-chip')).toHaveTextContent(
      'CRITICAL — BELOW FLOOR',
    );
  });

  // ── Regime chip ──────────────────────────────────────────────────────────
  it('shows regime as a separate chip element', () => {
    mockHealthy();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-regime-chip')).toHaveTextContent('CAUTION');
  });

  it('shows CLEAR in regime chip for CLEAR regime', () => {
    mockClearTransition();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-regime-chip')).toHaveTextContent('CLEAR');
  });

  // ── Warning box class ────────────────────────────────────────────────────
  it('warning box has --critical modifier class when warning_level is CRITICAL', () => {
    mockBelowFloor();
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-warning-box')).toHaveClass(
      'atlas-fws-warning-box--critical',
    );
  });

  it('warning box has --amber modifier class when warning_level is AMBER', () => {
    mockHealthy({
      floor_status: 'AT_FLOOR',
      warning_level: 'AMBER',
      warning_message: 'At floor — no buffer available.',
    });
    render(<CashFloorPanel />);
    expect(screen.getByTestId('cash-floor-warning-box')).toHaveClass(
      'atlas-fws-warning-box--amber',
    );
  });
});


