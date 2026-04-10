'use client';

import { useState } from 'react';

import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useMarketConditions } from '@/lib/hooks/use-market-conditions';
import { useTickers } from '@/lib/hooks/use-tickers';
import { cn } from '@/lib/utils';
import { computeRegimeOutput, determineRule } from '@/lib/utils/regime-rules';
import type { RegimeOutput, RegimeRule } from '@/lib/utils/regime-rules';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of score-bar segments spanning the 0-100 scale. */
const SCORE_BAR_SEGMENTS = 10;

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
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Regime Modifier panel — computes the market-regime adjustment (Brent crude,
 * VIX, active-war flag) and applies it to the base Framework Score from the
 * existing cache. The panel does not call the per-ticker regime-modifier API.
 */
export function RegimeModifierPanel({ ticker }: RegimeModifierPanelProps) {
  const [activeWar, setActiveWar] = useState(false);

  const activeTicker = ticker.trim().length > 0;

  const {
    data: fw,
    isLoading: isLoadingFw,
    isError: isErrorFw,
    error: fwError,
  } = useFrameworkScore(ticker);

  const { data: market, isLoading: isLoadingMarket, isError: isErrorMarket } =
    useMarketConditions();
  const { data: tickers } = useTickers();

  // Avoid loading UI for an empty ticker: Framework score query is disabled in
  // that state, while market conditions remain globally cached.
  const isLoading = activeTicker && (isLoadingFw || isLoadingMarket);
  const isError = (activeTicker && isErrorFw) || isErrorMarket;
  const hasData = activeTicker && fw !== undefined && market !== undefined;

  let brentConsecutiveBelow95 = false;
  if (market?.brent_price != null && market?.brent_prev_price != null) {
    brentConsecutiveBelow95 = market.brent_price < 95 && market.brent_prev_price < 95;
  }

  const rule = hasData
    ? determineRule(
        activeWar,
        market.brent_price,
        market.vix_value,
        brentConsecutiveBelow95,
      )
    : null;

  const output = hasData ? computeRegimeOutput(rule, fw.final_score) : null;
  const activeTickerRow = (tickers ?? []).find((row) => row.ticker === ticker);
  const positionValue = activeTickerRow?.position_value ?? null;
  const minCashUsd = output !== null && positionValue !== null ? positionValue * output.minCashPct : null;
  const maxCashUsd = output !== null && positionValue !== null ? positionValue * output.maxCashPct : null;

  const errorMsg = fwError instanceof Error ? fwError.message : 'Failed to load regime data.';

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
        {isError && <ErrorState message={errorMsg} />}
        {!isLoading && !isError && hasData && output !== null && (
          <RegimeContent
            brentPrice={market.brent_price}
            vixValue={market.vix_value}
            activeWar={activeWar}
            baseScore={fw.final_score}
            output={output}
            minCashUsd={minCashUsd}
            maxCashUsd={maxCashUsd}
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
  baseScore: number;
  output: RegimeOutput;
  minCashUsd: number | null;
  maxCashUsd: number | null;
};

function RegimeContent({
  brentPrice,
  vixValue,
  activeWar,
  baseScore,
  output,
  minCashUsd,
  maxCashUsd,
}: RegimeContentProps) {
  const adjTone = scoreToTone(output.adjustedScore);
  const baseTone = scoreToTone(baseScore);
  const filledSegs = Math.round(output.adjustedScore / SCORE_BAR_SEGMENTS);
  const ruleTone = output.ruleTriggered !== null ? RULE_TONE[output.ruleTriggered] : '';

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
        {output.ruleTriggered !== null ? (
          <>
            <span className={cn('atlas-regime-rule-badge', ruleTone)} data-testid="regime-rule-badge">
              {RULE_LABEL[output.ruleTriggered]}
            </span>
            <span className={cn('atlas-regime-delta', ruleTone)} data-testid="regime-delta">
              {RULE_DELTA_LABEL[output.ruleTriggered]}
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
          <span className="atlas-regime-score-label">BASE</span>
          <span
            className={cn('atlas-regime-score-num atlas-regime-score-num--base', baseTone)}
            data-testid="regime-base-score"
          >
            {baseScore}
          </span>
        </div>

        <span className="atlas-regime-arrow" aria-hidden="true">
          →
        </span>

        <div className="atlas-regime-score-block">
          <span className="atlas-regime-score-label">ADJUSTED</span>
          <span className={cn('atlas-regime-score-num', adjTone)} data-testid="regime-adjusted-score">
            {output.adjustedScore}
          </span>
        </div>
      </div>

      <div
        className="atlas-fws-score-bar"
        aria-label={`Adjusted score: ${output.adjustedScore} out of 100`}
      >
        {Array.from({ length: SCORE_BAR_SEGMENTS }).map((_, i) => (
          <span
            key={i}
            className={cn('atlas-fws-score-seg', i < filledSegs ? adjTone : 'is-empty')}
          />
        ))}
      </div>

      {output.ruleTriggered !== null && (
        <div className="atlas-regime-cash-block" data-testid="regime-cash-block">
          <p className="atlas-regime-cash-title">CASH GUIDANCE</p>

          <div className="atlas-regime-cash-row">
            <span className="atlas-regime-cash-label">Required range</span>
            <span className="atlas-regime-cash-value" data-testid="regime-cash-pct">
              {(output.minCashPct * 100).toFixed(0)}%
              {' — '}
              {(output.maxCashPct * 100).toFixed(0)}% of position
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

      {output.outputText && (
        <div className="atlas-regime-output" data-testid="regime-output-text">
          {output.outputText.split('\n').map((line, i) => (
            <p key={i} className="atlas-regime-output-line">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
