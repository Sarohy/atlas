'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';
import type { RegimeModifierResponse } from '@/lib/schemas/regime-modifier';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of score-bar segments spanning the 0–100 scale. */
const SCORE_BAR_SEGMENTS = 10;

/** CSS tone class for each rule. */
const RULE_TONE: Record<number, string> = {
  1: 'is-red',
  2: 'is-orange',
  3: 'is-green',
};

/** Human-readable label for each regime rule. */
const RULE_LABEL: Record<number, string> = {
  1: 'RULE 1 — CRISIS',
  2: 'RULE 2 — CAUTION',
  3: 'RULE 3 — CLEAR',
};

/** Score delta label per rule. */
const RULE_DELTA_LABEL: Record<number, string> = {
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
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Regime Modifier panel — applies market-regime rules (Brent crude, VIX,
 * active-war flag) to the base Framework Score and returns an adjusted
 * conviction score with per-position cash guidance.
 *
 * The war toggle lives inside this panel and feeds directly into the query
 * key, so toggling it immediately triggers a fresh fetch.
 */
export function RegimeModifierPanel({ ticker }: RegimeModifierPanelProps) {
  const [activeWar, setActiveWar] = useState(false);
  const { data, isLoading, isError, error } = useRegimeModifier(ticker, activeWar);

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel"
      data-testid="regime-modifier-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 2</h2>

        {/* War toggle — always visible in the header */}
        <button
          aria-label={activeWar ? 'Deactivate war zone flag' : 'Activate war zone flag'}
          aria-pressed={activeWar}
          className={cn('atlas-regime-war-btn', activeWar && 'is-active')}
          data-testid="regime-war-toggle"
          type="button"
          onClick={() => setActiveWar((v) => !v)}
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
        {isError && (
          <ErrorState
            message={
              error instanceof Error ? error.message : 'Failed to load regime modifier data.'
            }
          />
        )}
        {!isLoading && !isError && data && <RegimeContent data={data} />}
        {!isLoading && !isError && !data && ticker && <EmptyState ticker={ticker} />}
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
      Fetching Brent & VIX…
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

function RegimeContent({ data }: { data: RegimeModifierResponse }) {
  const adjTone = scoreToTone(data.adjusted_score);
  const baseTone = scoreToTone(data.base_score);
  const filledSegs = Math.round(data.adjusted_score / SCORE_BAR_SEGMENTS);
  const ruleTone = data.rule_triggered !== null ? (RULE_TONE[data.rule_triggered] ?? 'is-yellow') : '';

  return (
    <div className="atlas-regime-content" data-testid="regime-content">

      {/* ── Market conditions row ── */}
      <div className="atlas-regime-market-row">
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">BRENT</span>
          <span className="atlas-regime-stat-value" data-testid="regime-brent">
            {data.brent_price !== null ? `$${data.brent_price.toFixed(2)}` : '—'}
          </span>
        </div>
        <div className="atlas-regime-stat-divider" />
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">VIX</span>
          <span className="atlas-regime-stat-value" data-testid="regime-vix">
            {data.vix_value !== null ? data.vix_value.toFixed(2) : '—'}
          </span>
        </div>
        {data.active_war && (
          <>
            <div className="atlas-regime-stat-divider" />
            <div className="atlas-regime-stat">
              <span className={cn('atlas-frameworks-pill is-red atlas-regime-war-pill')} data-testid="regime-war-badge">
                WAR ACTIVE
              </span>
            </div>
          </>
        )}
      </div>

      {/* ── Rule badge ── */}
      <div className="atlas-regime-rule-row" data-testid="regime-rule-row">
        {data.rule_triggered !== null ? (
          <>
            <span className={cn('atlas-regime-rule-badge', ruleTone)} data-testid="regime-rule-badge">
              {RULE_LABEL[data.rule_triggered]}
            </span>
            <span className={cn('atlas-regime-delta', ruleTone)} data-testid="regime-delta">
              {RULE_DELTA_LABEL[data.rule_triggered]}
            </span>
          </>
        ) : (
          <span className="atlas-regime-rule-badge is-muted" data-testid="regime-rule-badge">
            NORMAL MARKET
          </span>
        )}
      </div>

      {/* ── Score adjustment hero ── */}
      <div className="atlas-regime-score-hero">
        <div className="atlas-regime-score-block">
          <span className="atlas-regime-score-label">BASE</span>
          <span className={cn('atlas-regime-score-num atlas-regime-score-num--base', baseTone)} data-testid="regime-base-score">
            {data.base_score}
          </span>
        </div>

        <span className="atlas-regime-arrow" aria-hidden="true">→</span>

        <div className="atlas-regime-score-block">
          <span className="atlas-regime-score-label">ADJUSTED</span>
          <span className={cn('atlas-regime-score-num', adjTone)} data-testid="regime-adjusted-score">
            {data.adjusted_score}
          </span>
        </div>
      </div>

      {/* ── Score bar for adjusted score ── */}
      <div
        className="atlas-fws-score-bar"
        aria-label={`Adjusted score: ${data.adjusted_score} out of 100`}
      >
        {Array.from({ length: SCORE_BAR_SEGMENTS }).map((_, i) => (
          <span
            key={i}
            className={cn('atlas-fws-score-seg', i < filledSegs ? adjTone : 'is-empty')}
          />
        ))}
      </div>

      {/* ── Cash guidance ── */}
      {data.rule_triggered !== null && (
        <div className="atlas-regime-cash-block" data-testid="regime-cash-block">
          <p className="atlas-regime-cash-title">CASH GUIDANCE</p>

          <div className="atlas-regime-cash-row">
            <span className="atlas-regime-cash-label">Required range</span>
            <span className="atlas-regime-cash-value" data-testid="regime-cash-pct">
              {(data.min_cash_pct * 100).toFixed(0)}%
              {' — '}
              {(data.max_cash_pct * 100).toFixed(0)}% of position
            </span>
          </div>

          {data.min_cash_usd !== null && data.max_cash_usd !== null && (
            <div className="atlas-regime-cash-row">
              <span className="atlas-regime-cash-label">USD amount</span>
              <span className="atlas-regime-cash-value" data-testid="regime-cash-usd">
                {formatUsd(data.min_cash_usd)} — {formatUsd(data.max_cash_usd)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── Output text instruction ── */}
      {data.output_text && (
        <div className="atlas-regime-output" data-testid="regime-output-text">
          {data.output_text.split('\n').map((line, i) => (
            <p key={i} className="atlas-regime-output-line">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
