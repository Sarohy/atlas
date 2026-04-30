import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { RegimeModifierPanel } from '@/components/frameworks/regime-modifier-panel';

const useRegimeModifierMock = vi.fn();

vi.mock('@/lib/hooks/use-regime-modifier', () => ({
  useRegimeModifier: (...args: unknown[]) => useRegimeModifierMock(...args),
}));

function renderPanel(ticker = 'AAPL') {
  return render(
    <RegimeModifierPanel
      ticker={ticker}
      geopoliticalState="ACTIVE_RISK"
      onGeopoliticalStateChange={vi.fn()}
    />,
  );
}

describe('RegimeModifierPanel', () => {
  it('renders the panel header', () => {
    useRegimeModifierMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    renderPanel();
    expect(screen.getByText('Framework 2')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    useRegimeModifierMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    renderPanel();
    expect(screen.getByTestId('regime-loading')).toBeInTheDocument();
  });

  it('renders regime content after data resolves', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-content')).toBeInTheDocument();
  });

  it('displays Brent crude price', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-brent')).toHaveTextContent('$97.50');
  });

  it('displays VIX value', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-vix')).toHaveTextContent('27.30');
  });

  it('shows the determination text', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-determination')).toHaveTextContent('CAUTION regime from');
  });

  it('does NOT show GEO PENALTY ACTIVE badge when special_case_active is false', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.queryByTestId('regime-geo-penalty-badge')).not.toBeInTheDocument();
  });

  it('shows GEO PENALTY ACTIVE badge when special_case_active is true', () => {
    mockLoadedRegimeEscalating();
    renderPanel();

    expect(screen.getByTestId('regime-geo-penalty-badge')).toHaveTextContent('GEO PENALTY ACTIVE');
  });

  it('does not fetch when ticker is empty', () => {
    useRegimeModifierMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPanel('');
    expect(screen.queryByTestId('regime-loading')).not.toBeInTheDocument();
  });

  it('does not render a direct soft caution picker', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.queryByRole('button', { name: /soft caution/i })).not.toBeInTheDocument();
  });
});

function mockLoadedRegime() {
  useRegimeModifierMock.mockReturnValue({
    data: {
      brent_consecutive_below_95_count: 2,
      brent_price: 97.5,
      vix_value: 27.3,
      rule: 'CAUTION',
      effective_regime: 'CAUTION',
      modifier: -5,
      geopolitical_state: 'ACTIVE_RISK',
      determination_text: 'CAUTION regime from Brent/VIX data. Brent streak below $95: 2. Geo flag: ACTIVE_RISK. Modifier: -5.',
      brent_condition: '$97.50 — $95-110 (CAUTION trigger)',
      vix_condition: '27.30 — 24-35 (CAUTION trigger)',
      geo_condition: 'ACTIVE_RISK',
      trigger_logic: 'OR — either Brent or VIX triggers',
      modifier_reason: 'CAUTION + ACTIVE RISK → −5',
      special_case_active: false,
      cash_floor_pct: 0.20,
    },
    isLoading: false,
    isError: false,
    error: null,
  });
}

function mockLoadedRegimeEscalating() {
  useRegimeModifierMock.mockReturnValue({
    data: {
      brent_consecutive_below_95_count: 0,
      brent_price: 97.5,
      vix_value: 27.3,
      rule: 'CAUTION',
      effective_regime: 'CAUTION',
      modifier: -7,
      geopolitical_state: 'ESCALATING',
      determination_text: 'CAUTION regime from Brent/VIX data. Brent streak below $95: 0. Geo flag: ESCALATING. Modifier: -7. GEO PENALTY ACTIVE: CAUTION + ESCALATING geo → −7.',
      brent_condition: '$97.50 — $95-110 (CAUTION trigger)',
      vix_condition: '27.30 — 24-35 (CAUTION trigger)',
      geo_condition: 'ESCALATING',
      trigger_logic: 'OR — either Brent or VIX triggers',
      modifier_reason: 'CAUTION + Escalating geo → −7',
      special_case_active: true,
      cash_floor_pct: 0.20,
    },
    isLoading: false,
    isError: false,
    error: null,
  });
}


