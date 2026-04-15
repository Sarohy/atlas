'use client';

import { useState } from 'react';

import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';
import { cn } from '@/lib/utils';
import type { RegimeRule } from '@/lib/utils/regime-rules';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** CSS tone class for each rule. */
const RULE_TONE: Record<RegimeRule, string> = {
  1: 'is-red',
  2: 'is-orange',
  3: 'is-green',
};

/** Human-readable label for each regime rule. */
const RULE_LABEL: Record<RegimeRule, string> = {
  1: 'RULE 1 — CRISIS',
  2: 'RULE 2 — CAUTION',
  3: 'RULE 3 — CLEAR',
};

/** Score delta label per rule. */
const RULE_DELTA_LABEL: Record<RegimeRule, string> = {
  1: '−10 pts',
  2: '−5 pts',
  3: '+5 pts',
};

/** CSS tone class derived from adjusted score (mirrors action-tone logic). */
function scoreToTone(score: number): string {
  if (score >= 90) return 'is-green';
  if (score >= 80) return 'is-cyan';
  if (score >= 70) return 'is-yellow';
  if (score >= 60) return 'is-orange';
  return 'is-red';
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type RegimeModifierPanelProps = {
  /** Active ticker symbol driven by the shared selector above the panels. */
  ticker: string;
  /**
   * When provided the component acts as a controlled input — the parent owns
   * the war-zone state and the panel's toggle calls ``onToggleWar`` instead
   * of managing its own internal state.
   */
  activeWar?: boolean;
  onToggleWar?: () => void;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/** Regime Modifier panel driven by the backend regime-modifier response. */
export function RegimeModifierPanel({
  ticker,
  activeWar: activeWarProp,
  onToggleWar,
}: RegimeModifierPanelProps) {
  const [internalWar, setInternalWar] = useState(false);

  // Support both controlled (activeWar/onToggleWar from parent) and
  // uncontrolled (internal state) usage so existing usages without props
  // continue to work.
  const isControlled = activeWarProp !== undefined && onToggleWar !== undefined;
  const activeWar = isControlled ? activeWarProp : internalWar;
  const handleToggleWar = isControlled ? onToggleWar : () => setInternalWar((v) => !v);

  const activeTicker = ticker.trim().length > 0;

  const {
    data: regime,
    isLoading,
    isError,
    error,
  } = useRegimeModifier(ticker, activeWar);
  const hasData = activeTicker && regime !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load regime data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel"
      data-testid="regime-modifier-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 2</h2>

        <button
          aria-label={activeWar ? 'Deactivate war zone flag' : 'Activate war zone flag'}
          aria-pressed={activeWar}
          className={cn('atlas-regime-war-btn', activeWar && 'is-active')}
          data-testid="regime-war-toggle"
          type="button"
          onClick={handleToggleWar}
        >
          <span className="atlas-regime-war-icon" aria-hidden="true">
            ⚑
          </span>
          {activeWar ? 'WAR ACTIVE' : 'WAR ZONE'}
        </button>

        <span className="atlas-fws-subtitle">Brent · VIX · War → Score</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && <LoadingState />}
        {isError && <ErrorState message={errorMsg} />}
        {!isLoading && !isError && hasData && (
          <RegimeContent
            brentPrice={regime.brent_price}
            vixValue={regime.vix_value}
            activeWar={activeWar}
            adjustedScore={regime.adjusted_score}
            ruleTriggered={regime.rule_triggered}
            ruleName={regime.rule}
            minCashPct={regime.min_cash_pct}
            maxCashPct={regime.max_cash_pct}
            minCashUsd={regime.min_cash_usd}
            maxCashUsd={regime.max_cash_usd}
            outputText={regime.output_text}
          />
        )}
        {!isLoading && !isError && !hasData && activeTicker && <EmptyState ticker={ticker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// State components
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <p className="atlas-fws-state-msg" data-testid="regime-loading">
      Fetching Brent & VIX...
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="regime-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-fws-state-msg" data-testid="regime-empty">
      No data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

type RegimeContentProps = {
  brentPrice: number | null;
  vixValue: number | null;
  activeWar: boolean;
  adjustedScore: number;
  ruleTriggered: RegimeRule | null;
  ruleName: string;
  minCashPct: number;
  maxCashPct: number;
  minCashUsd: number | null;
  maxCashUsd: number | null;
  outputText: string;
};

function RegimeContent({
  brentPrice,
  vixValue,
  activeWar,
  adjustedScore,
  ruleTriggered,
  ruleName,
  minCashPct,
  maxCashPct,
  minCashUsd,
  maxCashUsd,
  outputText,
}: RegimeContentProps) {
  const adjTone = scoreToTone(adjustedScore);
  const ruleTone = ruleTriggered !== null ? RULE_TONE[ruleTriggered] : '';

  return (
    <div className="atlas-regime-content" data-testid="regime-content">
      <div className="atlas-regime-market-row">
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">BRENT</span>
          <span className="atlas-regime-stat-value" data-testid="regime-brent">
            {brentPrice !== null ? `$${brentPrice.toFixed(2)}` : '-'}
          </span>
        </div>
        <div className="atlas-regime-stat-divider" />
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">VIX</span>
          <span className="atlas-regime-stat-value" data-testid="regime-vix">
            {vixValue !== null ? vixValue.toFixed(2) : '-'}
          </span>
        </div>
        {activeWar && (
          <>
            <div className="atlas-regime-stat-divider" />
            <div className="atlas-regime-stat">
              <span
                className={cn('atlas-frameworks-pill is-red atlas-regime-war-pill')}
                data-testid="regime-war-badge"
              >
                WAR ACTIVE
              </span>
            </div>
          </>
        )}
      </div>

      <div className="atlas-regime-rule-row" data-testid="regime-rule-row">
        {ruleTriggered !== null ? (
          <>
            <span className={cn('atlas-regime-rule-badge', ruleTone)} data-testid="regime-rule-badge">
              {RULE_LABEL[ruleTriggered]}
            </span>
            <span className={cn('atlas-regime-delta', ruleTone)} data-testid="regime-delta">
              {RULE_DELTA_LABEL[ruleTriggered]}
            </span>
          </>
        ) : (
          <span className="atlas-regime-rule-badge is-muted" data-testid="regime-rule-badge">
            NORMAL MARKET
          </span>
        )}
      </div>

      <div className="atlas-regime-score-hero">
        <div className="atlas-regime-score-block">
          <span className="atlas-regime-score-label">RULE</span>
          <span className={cn('atlas-regime-score-num', adjTone)} data-testid="regime-rule-value">
            {ruleName}
          </span>
        </div>
      </div>

      {ruleTriggered !== null && (
        <div className="atlas-regime-cash-block" data-testid="regime-cash-block">
          <p className="atlas-regime-cash-title">CASH GUIDANCE</p>

          <div className="atlas-regime-cash-row">
            <span className="atlas-regime-cash-label">Required range</span>
            <span className="atlas-regime-cash-value" data-testid="regime-cash-pct">
              {(minCashPct * 100).toFixed(0)}%
              {' — '}
              {(maxCashPct * 100).toFixed(0)}% of position
            </span>
          </div>

          {minCashUsd !== null && maxCashUsd !== null && (
            <div className="atlas-regime-cash-row">
              <span className="atlas-regime-cash-label">USD amount</span>
              <span className="atlas-regime-cash-value" data-testid="regime-cash-usd">
                {formatUsd(minCashUsd)} — {formatUsd(maxCashUsd)}
              </span>
            </div>
          )}
        </div>
      )}

      {outputText && (
        <div className="atlas-regime-output" data-testid="regime-output-text">
          {outputText.split('\n').map((line, i) => (
            <p key={i} className="atlas-regime-output-line">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
