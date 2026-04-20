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
      geopoliticalState="ACTIVE"
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

  it('displays the automatic regime badge', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-automatic-regime')).toHaveTextContent('CAUTION');
  });

  it('shows the effective regime label', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-effective-regime')).toHaveTextContent('SOFT CAUTION');
  });

  it('shows the consecutive Brent close count used by the automatic regime logic', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-brent-streak')).toHaveTextContent('2');
  });

  it('shows the active geopolitical gate from the shared morning briefing state', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-geopolitical-state')).toHaveTextContent('ACTIVE');
  });

  it('renders the three-state geopolitical toggle inside Framework 2', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByRole('button', { name: 'None' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'De-escalating' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Active' })).toBeInTheDocument();
  });

  it('shows the clear determination summary', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.getByTestId('regime-determination')).toHaveTextContent(
      'Geopolitical flag ACTIVE adds a secondary gate',
    );
  });

  it('does not render a direct soft caution picker', () => {
    mockLoadedRegime();
    renderPanel();

    expect(screen.queryByRole('button', { name: /soft caution/i })).not.toBeInTheDocument();
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
});

function mockLoadedRegime() {
  useRegimeModifierMock.mockReturnValue({
    data: {
      brent_consecutive_below_95_count: 2,
      brent_price: 97.5,
      determination_text:
        'Automatic regime CAUTION from Brent/VIX data. Brent streak below $95: 2. Geopolitical flag ACTIVE adds a secondary gate, so the displayed regime is SOFT CAUTION.',
      effective_regime: 'SOFT CAUTION',
      geopolitical_state: 'ACTIVE',
      rule: 'CAUTION',
      vix_value: 27.3,
    },
    isLoading: false,
    isError: false,
    error: null,
  });
}
