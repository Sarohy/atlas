'use client';

import { useState } from 'react';

import { useTrancheSizing } from '@/lib/hooks/use-tranche-sizing';
import type { TrancheSizingResponse } from '@/lib/schemas/tranche-sizing';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Value the backend returns for a tranche gate that did not fire. */
const BLOCKED = 'Blocked';

/** Display label for each tranche key. */
const TRANCHE_LABELS: Record<keyof Omit<TrancheSizingResponse, 'ticker'>, string> = {
  t1: 'T1 · Initial Catalyst',
  t2: 'T2 · Regime CAUTION',
  t3: 'T3 · Regime CLEAR',
  t4: 'T4 · Iran Resolution',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type TrancheSizingPanelProps = {
  /** Active ticker symbol driven by the shared selector above the panels. */
  ticker: string;
  /**
   * Framework 2 regime rule already held by the parent — passed through to
   * avoid a second independent regime fetch.
   * Defaults to "NORMAL" (all regime gates blocked) until F2 data loads.
   */
  regimeRule: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 4 — Tranche Sizing panel.
 *
 * Two header toggles let the investor mark the catalyst and Iran resolution
 * status directly in the panel; the regime rule is injected from Framework 2
 * so T2/T3 are always in sync with what Framework 2 is displaying.
 */
export function TrancheSizingPanel({ ticker, regimeRule }: TrancheSizingPanelProps) {
  const [initialCatalyst, setInitialCatalyst] = useState<'yes' | 'no'>('no');
  const [iranConfirmed, setIranConfirmed] = useState(false);

  const activeTicker = ticker.trim().length > 0;
  const iranResolution = iranConfirmed ? 'confirmed' : null;

  const { data, isLoading, isError, error } = useTrancheSizing(
    ticker,
    initialCatalyst,
    regimeRule,
    iranResolution,
  );

  const hasData = activeTicker && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load framework 4 data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-tranche-panel"
      data-testid="tranche-sizing-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 4</h2>

        <button
          aria-label={
            initialCatalyst === 'yes'
              ? 'Mark initial catalyst as not confirmed'
              : 'Mark initial catalyst as confirmed'
          }
          aria-pressed={initialCatalyst === 'yes'}
          className={cn('atlas-regime-war-btn', initialCatalyst === 'yes' && 'is-active')}
          data-testid="tranche-catalyst-toggle"
          type="button"
          onClick={() => setInitialCatalyst((c) => (c === 'yes' ? 'no' : 'yes'))}
        >
          {initialCatalyst === 'yes' ? 'CATALYST: YES' : 'CATALYST: NO'}
        </button>

        <button
          aria-label={
            iranConfirmed
              ? 'Mark Iran resolution as unconfirmed'
              : 'Mark Iran resolution as confirmed'
          }
          aria-pressed={iranConfirmed}
          className={cn('atlas-regime-war-btn', iranConfirmed && 'is-active')}
          data-testid="tranche-iran-toggle"
          type="button"
          onClick={() => setIranConfirmed((v) => !v)}
        >
          {iranConfirmed ? 'IRAN: CONFIRMED' : 'IRAN: PENDING'}
        </button>

        <span className="atlas-fws-subtitle">Catalyst → Tranche Sizing</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="tranche-loading">
            Computing tranches...
          </p>
        )}
        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="tranche-error"
          >
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && (
          <TrancheContent data={data} regimeRule={regimeRule} />
        )}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="tranche-empty">
            No tranche data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Tranche content
// ---------------------------------------------------------------------------

type TrancheContentProps = {
  data: TrancheSizingResponse;
  regimeRule: string;
};

function TrancheContent({ data, regimeRule }: TrancheContentProps) {
  const tranches = (
    ['t1', 't2', 't3', 't4'] as const
  ).map((key) => ({
    key,
    label: TRANCHE_LABELS[key],
    value: data[key],
    isActive: data[key] !== BLOCKED,
  }));

  return (
    <div className="atlas-tranche-content" data-testid="tranche-content">
      <div className="atlas-regime-rule-row" data-testid="tranche-regime-row">
        <span
          className="atlas-regime-rule-badge is-muted"
          data-testid="tranche-regime-badge"
        >
          REGIME: {regimeRule}
        </span>
      </div>

      <div className="atlas-regime-cash-block">
        <p className="atlas-regime-cash-title">DEPLOYMENT TRANCHES</p>

        {tranches.map(({ key, label, value, isActive }) => (
          <div
            className="atlas-regime-cash-row"
            data-testid={`tranche-row-${key}`}
            key={key}
          >
            <span className="atlas-regime-cash-label">{label}</span>
            <span
              className={cn(
                'atlas-regime-cash-value',
                isActive ? 'is-active' : 'is-blocked',
              )}
              data-testid={`tranche-value-${key}`}
            >
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
