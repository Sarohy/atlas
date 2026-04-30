'use client';

import { useEffect, useState } from 'react';

import { useTrancheSizing, useConfirmTranche } from '@/lib/hooks/use-tranche-sizing';
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
  t1: 'T1 · Catalyst',
  t2: 'T2 · Brent below $110',
  t3: 'T3 · Clear+Gate',
  t4: 'T4 · Iran',
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
  /** Brent crude price in USD/bbl from F2 data. T2 unlocks when < $110. */
  brentPrice?: number | null;
  /** Consecutive Brent closes below $95 from F2 data. Auto-detects signal 2. */
  brentConsecutiveBelow95Count?: number;
  /** Current geopolitical state from F2. Auto-detects signal 5 when RESOLVED. */
  geopoliticalState?: string;
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
export function TrancheSizingPanel({
  ticker,
  regimeRule,
  brentPrice = null,
  brentConsecutiveBelow95Count = 0,
  geopoliticalState = 'NONE',
}: TrancheSizingPanelProps) {
  const [initialCatalyst, setInitialCatalyst] = useState<'yes' | 'no'>('no');
  const [iranConfirmed, setIranConfirmed] = useState(false);

  const activeTicker = ticker.trim().length > 0;
  const iranResolution = iranConfirmed ? 'confirmed' : null;

  const { data, isLoading, isError, error } = useTrancheSizing(
    ticker,
    initialCatalyst,
    regimeRule,
    iranResolution,
    brentConsecutiveBelow95Count,
    geopoliticalState,
    brentPrice,
  );

  const { mutate: confirmTranche, isPending: isConfirming } = useConfirmTranche(ticker);

  const hasData = activeTicker && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load framework 4 data.';

  // BUG C fix: single source of truth for CATALYST display.
  // When API data is available, read catalyst state from data.catalyst_confirmed
  // (mirrors data.t1_fired). Fall back to local toggle only before first fetch.
  const catalystActive = hasData ? data.catalyst_confirmed : (initialCatalyst === 'yes');

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-tranche-panel"
      data-testid="tranche-sizing-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 4</h2>

        <button
          aria-label={
            catalystActive
              ? 'Mark initial catalyst as not confirmed'
              : 'Mark initial catalyst as confirmed'
          }
          aria-pressed={catalystActive}
          className={cn('atlas-regime-war-btn', catalystActive && 'is-active')}
          data-testid="tranche-catalyst-toggle"
          type="button"
          onClick={() => setInitialCatalyst((c) => (c === 'yes' ? 'no' : 'yes'))}
        >
          {catalystActive ? 'CATALYST: YES' : 'CATALYST: NO'}
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
          <TrancheContent
            data={data}
            regimeRule={regimeRule}
            brentPrice={brentPrice}
            onConfirmTranche={confirmTranche}
            isConfirming={isConfirming}
          />
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
// Beta cap suppression box (Framework 13)
// ---------------------------------------------------------------------------

type BetaCapBoxProps = {
  reason: string;
  message: string;
};

function BetaCapBox({ reason, message }: BetaCapBoxProps) {
  return (
    <div className="atlas-tranche-cap-box" data-testid="tranche-beta-cap-box">
      <p className="atlas-tranche-cap-title">Beta Cap Active (F13)</p>
      <p className="atlas-tranche-cap-message">{message}</p>
      <div className="atlas-tranche-cap-row">
        <span className="atlas-tranche-cap-key">Reason</span>
        <span className="atlas-tranche-cap-val" data-testid="tranche-beta-cap-reason">
          {reason}
        </span>
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
// Auto-trigger confirmation modal (Framework 17)
// ---------------------------------------------------------------------------

type TrancheConfirmModalProps = {
  tranche: 't2' | 't3';
  amount: string;
  brentPrice?: number | null;
  signalsConfirmed?: number;
  onConfirm: () => void;
  onOverride: () => void;
  isConfirming: boolean;
};

function TrancheConfirmModal({
  tranche,
  amount,
  brentPrice,
  signalsConfirmed,
  onConfirm,
  onOverride,
  isConfirming,
}: TrancheConfirmModalProps) {
  const isT2 = tranche === 't2';
  const label = isT2 ? 'T2' : 'T3';
  const trigger = isT2
    ? `Brent closed at $${brentPrice?.toFixed(2) ?? '—'} — below $110 threshold`
    : `CLEAR regime confirmed · AND gate: ${signalsConfirmed ?? 0} of 5 signals passed`;

  return (
    <div
      className="atlas-tranche-modal-backdrop"
      data-testid={`tranche-confirm-modal-${tranche}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={`tranche-modal-title-${tranche}`}
    >
      <div className="atlas-tranche-modal">
        <p
          className="atlas-tranche-modal-title"
          id={`tranche-modal-title-${tranche}`}
        >
          {label} Auto-Triggered
        </p>
        <p className="atlas-tranche-modal-trigger">{trigger}</p>
        <p className="atlas-tranche-modal-amount">
          Deploy <strong>{amount}</strong>?
        </p>
        <div className="atlas-tranche-modal-actions">
          <button
            className="atlas-tranche-modal-confirm"
            data-testid={`tranche-confirm-btn-${tranche}`}
            disabled={isConfirming}
            type="button"
            onClick={onConfirm}
          >
            {isConfirming ? 'Confirming…' : 'Confirm'}
          </button>
          <button
            className="atlas-tranche-modal-override"
            data-testid={`tranche-override-btn-${tranche}`}
            disabled={isConfirming}
            type="button"
            onClick={onOverride}
          >
            Override
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tranche content (cap inactive)
// ---------------------------------------------------------------------------

type TrancheContentProps = {
  data: TrancheSizingResponse;
  regimeRule: string;
  brentPrice?: number | null;
  onConfirmTranche: (tranche: 't2' | 't3') => void;
  isConfirming: boolean;
};

function TrancheContent({ data, regimeRule, brentPrice, onConfirmTranche, isConfirming }: TrancheContentProps) {
  const isClear = regimeRule.toUpperCase() === 'CLEAR';

  // Local dismissed state so override suppresses the modal for this session.
  const [t2Dismissed, setT2Dismissed] = useState(false);
  const [t3Dismissed, setT3Dismissed] = useState(false);

  // Re-open modal if pending state changes (e.g. after query refresh changes conditions).
  useEffect(() => {
    if (!data.t2_pending) setT2Dismissed(false);
  }, [data.t2_pending]);
  useEffect(() => {
    if (!data.t3_pending) setT3Dismissed(false);
  }, [data.t3_pending]);

  const showT2Modal = data.t2_pending && !t2Dismissed;
  const showT3Modal = data.t3_pending && !t3Dismissed;

  return (
    <div className="atlas-tranche-content" data-testid="tranche-content">
      {/* Auto-trigger confirmation modals (Framework 17) */}
      {showT2Modal && (
        <TrancheConfirmModal
          tranche="t2"
          amount={data.t2 ?? '20-25% of available cash'}
          brentPrice={brentPrice}
          onConfirm={() => { onConfirmTranche('t2'); setT2Dismissed(true); }}
          onOverride={() => setT2Dismissed(true)}
          isConfirming={isConfirming}
        />
      )}
      {showT3Modal && (
        <TrancheConfirmModal
          tranche="t3"
          amount={data.t3 ?? '30-40% of available cash'}
          signalsConfirmed={data.signals_confirmed}
          onConfirm={() => { onConfirmTranche('t3'); setT3Dismissed(true); }}
          onOverride={() => setT3Dismissed(true)}
          isConfirming={isConfirming}
        />
      )}
      {/* Framework 14 concentration cap suppression */}
      {data.cap_active && (
        <CapBox
          positionWeight={data.position_weight}
          message={data.message ?? 'Adds blocked by concentration cap - tranche sizing N/A'}
        />
      )}

      {/* Framework 13 beta cap suppression */}
      {data.beta_cap_active && !data.cap_active && (
        <BetaCapBox
          reason={data.beta_cap_reason ?? 'Beta cap active — tranche sizing N/A'}
          message={data.message ?? 'Adds blocked by beta cap - tranche sizing N/A'}
        />
      )}

      {/* Regime badge - only shown when neither cap is active */}
      {!data.cap_active && !data.beta_cap_active && (
        <div className="atlas-regime-rule-row" data-testid="tranche-regime-row">
          <span
            className="atlas-regime-rule-badge is-muted"
            data-testid="tranche-regime-badge"
          >
            REGIME: {regimeRule}
          </span>
        </div>
      )}

      {/* AND gate section - only when CLEAR regime and no cap active */}
      {!data.cap_active && !data.beta_cap_active && data.and_gate_active && (
        <AndGateSection
          andGatePassed={data.and_gate_passed}
          signalsConfirmed={data.signals_confirmed}
          signalsDetail={data.signals_detail}
        />
      )}

      {/* T3 waiting notice when CLEAR but gate blocked */}
      {!data.cap_active && !data.beta_cap_active && isClear && !data.and_gate_passed && (
        <p className="atlas-tranche-t3-waiting" data-testid="tranche-t3-waiting">
          T3 deployment waiting for AND gate — {data.signals_confirmed} of 5 signals confirmed
        </p>
      )}

      {/* Tranche rows - only when no cap is active */}
      {!data.cap_active && !data.beta_cap_active && (
        <div className="atlas-regime-cash-block">
          <p className="atlas-regime-cash-title">DEPLOYMENT TRANCHES</p>

          {(
            ['t1', 't2', 't3', 't4'] as const
          ).map((key) => {
            const value = data[key];
            const label = TRANCHE_LABELS[key];
            const isActive = value !== null && value !== BLOCKED;
            const isWaiting = key === 't1' && !data.t1_fired;
            const isBlockedByT1 = key !== 't1' && !data.t1_fired;
            // T1 fired: manual — operator decides the trigger.
            const isFiredT1 = key === 't1' && data.t1_fired;
            // T2/T3 fired: auto-triggered — operator confirmed the order.
            const isFiredT2 = key === 't2' && data.t2_fired;
            const isFiredT3 = key === 't3' && data.t3_fired;
            const isFired = isFiredT1 || isFiredT2 || isFiredT3;
            // T2/T3 pending: conditions met, modal shown — no ELIGIBLE chip.
            const isPendingT2 = key === 't2' && data.t2_pending;
            const isPendingT3 = key === 't3' && data.t3_pending;

            return (
              <div
                className="atlas-regime-cash-row"
                data-testid={`tranche-row-${key}`}
                key={key}
              >
                <span className="atlas-regime-cash-label">{label}</span>
                <div className="atlas-tranche-value-group">
                  {isFired ? (
                    <>
                      <span
                        className="atlas-tranche-fired-chip"
                        data-testid={`tranche-value-${key}`}
                      >
                        FIRED
                      </span>
                      <span
                        className="atlas-tranche-size-range"
                        data-testid={`tranche-size-${key}`}
                      >
                        {value}
                      </span>
                    </>
                  ) : isPendingT2 || isPendingT3 ? (
                    <span
                      className="atlas-tranche-pending-chip"
                      data-testid={`tranche-value-${key}`}
                    >
                      CONFIRMING
                    </span>
                  ) : (
                    <span
                      className={cn(
                        'atlas-regime-cash-value',
                        isActive ? 'is-active' : isWaiting ? 'is-waiting' : 'is-blocked',
                      )}
                      data-testid={`tranche-value-${key}`}
                    >
                      {isWaiting ? 'Waiting' : (value ?? 'N/A')}
                    </span>
                  )}
                  {isBlockedByT1 && (
                    <span
                      className="atlas-tranche-seq-reason"
                      data-testid={`tranche-seq-reason-${key}`}
                    >
                      Requires T1 first
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

