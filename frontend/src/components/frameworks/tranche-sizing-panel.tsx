'use client';

import { useState } from 'react';

import { useTrancheSizing } from '@/lib/hooks/use-tranche-sizing';
import type { SignalDetail, TrancheSizingResponse } from '@/lib/schemas/tranche-sizing';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Value the backend returns for a tranche gate that did not fire. */
const BLOCKED = 'Blocked';

/** Percentage representation of the concentration cap threshold. */
const CAP_THRESHOLD_PCT = '8%';

/** Display label for each tranche key. */
const TRANCHE_LABELS: Record<keyof Pick<TrancheSizingResponse, 't1' | 't2' | 't3' | 't4'>, string> = {
  t1: 'T1 · Initial Catalyst',
  t2: 'T2 · Regime CAUTION',
  t3: 'T3 · CLEAR + AND Gate',
  t4: 'T4 · Iran Resolution',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type TrancheSizingPanelProps = {
  /** Active ticker symbol driven by the shared selector above the panels. */
  ticker: string;
  /**
   * Framework 2 regime rule already held by the parent - passed through to
   * avoid a second independent regime fetch.
   * Defaults to "NORMAL" (all regime gates blocked) until F2 data loads.
   */
  regimeRule: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 4 - Tranche Sizing panel (v7.3.4).
 *
 * Shows concentration cap suppression when position >= 8% NAV, AND gate
 * status when regime is CLEAR, and T3 waiting indicator when gate is blocked.
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
// Concentration cap suppression box
// ---------------------------------------------------------------------------

type CapBoxProps = {
  positionWeight: number;
  message: string;
};

function CapBox({ positionWeight, message }: CapBoxProps) {
  const weightPct = (positionWeight * 100).toFixed(1);

  return (
    <div className="atlas-tranche-cap-box" data-testid="tranche-cap-box">
      <p className="atlas-tranche-cap-title">Concentration Cap Active</p>
      <p className="atlas-tranche-cap-message">{message}</p>
      <div className="atlas-tranche-cap-row">
        <span className="atlas-tranche-cap-key">Current weight</span>
        <span className="atlas-tranche-cap-val" data-testid="tranche-cap-weight">
          {weightPct}% NAV
        </span>
      </div>
      <div className="atlas-tranche-cap-row">
        <span className="atlas-tranche-cap-key">Soft cap threshold</span>
        <span className="atlas-tranche-cap-val">{CAP_THRESHOLD_PCT} NAV</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AND gate section (shown only when CLEAR regime)
// ---------------------------------------------------------------------------

type AndGateSectionProps = {
  andGatePassed: boolean;
  signalsConfirmed: number;
  signalsDetail: SignalDetail[];
};

function AndGateSection({ andGatePassed, signalsConfirmed, signalsDetail }: AndGateSectionProps) {
  return (
    <div className="atlas-tranche-and-gate" data-testid="tranche-and-gate">
      <div className="atlas-tranche-and-gate-header">
        <p className="atlas-tranche-and-gate-title">Framework 29 AND Gate</p>
        <span
          className={cn(
            'atlas-tranche-and-gate-status',
            andGatePassed ? 'is-passed' : 'is-blocked',
          )}
          data-testid="tranche-and-gate-status"
        >
          {andGatePassed ? 'PASSED' : 'BLOCKED'}
        </span>
      </div>
      <p className="atlas-tranche-and-gate-count" data-testid="tranche-signals-confirmed">
        {signalsConfirmed} of 5 signals confirmed
      </p>
      {signalsDetail.map((signal) => (
        <div className="atlas-tranche-signal-row" key={signal.signal_index}>
          <span
            className={cn(
              'atlas-tranche-signal-dot',
              signal.confirmed ? 'is-confirmed' : 'is-pending',
            )}
            data-testid={`tranche-signal-dot-${signal.signal_index}`}
          />
          <span
            className={cn(
              'atlas-tranche-signal-name',
              signal.confirmed && 'is-confirmed',
            )}
            data-testid={`tranche-signal-name-${signal.signal_index}`}
          >
            {signal.name}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tranche content (cap inactive)
// ---------------------------------------------------------------------------

type TrancheContentProps = {
  data: TrancheSizingResponse;
  regimeRule: string;
};

function TrancheContent({ data, regimeRule }: TrancheContentProps) {
  const isClear = regimeRule.toUpperCase() === 'CLEAR';

  return (
    <div className="atlas-tranche-content" data-testid="tranche-content">
      {/* Concentration cap suppression */}
      {data.cap_active && (
        <CapBox
          positionWeight={data.position_weight}
          message={data.message ?? 'Adds blocked by concentration cap - tranche sizing N/A'}
        />
      )}

      {/* Regime badge - only shown when cap is not active */}
      {!data.cap_active && (
        <div className="atlas-regime-rule-row" data-testid="tranche-regime-row">
          <span
            className="atlas-regime-rule-badge is-muted"
            data-testid="tranche-regime-badge"
          >
            REGIME: {regimeRule}
          </span>
        </div>
      )}

      {/* AND gate section - only when CLEAR regime and cap not active */}
      {!data.cap_active && data.and_gate_active && (
        <AndGateSection
          andGatePassed={data.and_gate_passed}
          signalsConfirmed={data.signals_confirmed}
          signalsDetail={data.signals_detail}
        />
      )}

      {/* T3 waiting notice when CLEAR but gate blocked */}
      {!data.cap_active && isClear && !data.and_gate_passed && (
        <p className="atlas-tranche-t3-waiting" data-testid="tranche-t3-waiting">
          T3 deployment waiting for AND gate — {data.signals_confirmed} of 5 signals confirmed
        </p>
      )}

      {/* Tranche rows - only when cap is not active */}
      {!data.cap_active && (
        <div className="atlas-regime-cash-block">
          <p className="atlas-regime-cash-title">DEPLOYMENT TRANCHES</p>

          {(
            ['t1', 't2', 't3', 't4'] as const
          ).map((key) => {
            const value = data[key];
            const label = TRANCHE_LABELS[key];
            const isActive = value !== null && value !== BLOCKED;

            return (
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
                  {value ?? 'N/A'}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

