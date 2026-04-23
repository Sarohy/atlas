'use client';

import { useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useAnalyst } from '@/lib/hooks/use-analyst';
import { useEarnings } from '@/lib/hooks/use-earnings';
import { useFundamental } from '@/lib/hooks/use-fundamental';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useMomentum } from '@/lib/hooks/use-momentum';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import type { FactorBreakdown, FrameworkScoreResponse } from '@/lib/schemas/framework-score';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of score-bar segments for the full 100-pt scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Inclusive lower bounds for Framework 3 / Score Action Map bands (v7.3.4). */
const ACTION_TIER1_MIN = 85;       // >= 85  → CORE / LEAPS ELIGIBLE
const ACTION_GREY_ZONE_MIN = 78;   // 78-84  → GREY ZONE
const ACTION_TIER2_MIN = 70;       // 70-77  → GTC ADDS PERMITTED
const ACTION_TIER3_MIN = 55;       // 55-69  → SMALL POSITION ONLY
                                   // < 55   → WATCHLIST

/** CSS tone class for each action tone string. */
const ACTION_TONE_CLASS: Record<string, string> = {
  'tone-green': 'is-green',
  'tone-purple': 'is-purple',
  'tone-blue': 'is-blue',
  'tone-yellow': 'is-yellow',
  'tone-red': 'is-red',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type FrameworkScorePanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
  /** Opens the detail-card overlay for the current framework selection. */
  onPreviewDetails: () => void;
  /** Score delta from Framework 2 regime modifier (-10, -5, 0, +5). */
  regimeModifier: number;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework Score panel — shows the final ATLAS conviction score that
 * aggregates F1-F5 with their Factor_Mapping_Guide weightings.
 *
 * Displayed above the individual factor panels (F1-F5) in the Frameworks
 * screen so the investor sees the combined verdict first.
 */
export function FrameworkScorePanel({ ticker, onPreviewDetails, regimeModifier }: FrameworkScorePanelProps) {
  const { data, isLoading, isError, error } = useFrameworkScore(ticker);
  const { data: momentumData } = useMomentum(ticker);
  const { data: earningsData } = useEarnings(ticker);
  const { data: analystData } = useAnalyst(ticker);
  const { data: optionsFlowData } = useOptionsFlow(ticker);
  const { data: fundamentalData } = useFundamental(ticker);

  const displayData = data
    ? buildDisplayFrameworkScore(data, {
        f1: momentumData?.f1_score,
        f2: earningsData?.f2_score,
        f3: analystData?.f3_score,
        f4: optionsFlowData?.f4_score,
        f5: fundamentalData?.f5_score,
      })
    : undefined;

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-fws-panel--half-width"
      data-testid="framework-score-panel"
    >
      <div className="atlas-fws-hover-overlay" data-testid="framework-score-hover-overlay">
        <button
          aria-label="Preview framework score details"
          className="atlas-fws-hover-eye"
          type="button"
          onClick={onPreviewDetails}
        >
          <svg
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </div>

      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 1</h2>
        <span className="atlas-fws-subtitle">F1 · F2 · F3 · F4 · F5 → Conviction</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && <LoadingState />}
        {isError && (
          <ErrorState
            message={
              error instanceof Error ? error.message : 'Failed to load framework score data.'
            }
          />
        )}
        {!isLoading && !isError && data && data.degraded && (
          <DegradedBanner
            flags={data.flags}
            factors={data.factors.filter((f) => !f.available)}
          />
        )}
        {!isLoading && !isError && displayData && (
          <FrameworkScoreContent data={displayData} regimeModifier={regimeModifier} />
        )}
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
    <p className="atlas-fws-state-msg" data-testid="fws-loading">
      Computing framework score…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="fws-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-fws-state-msg" data-testid="fws-empty">
      No framework score available for {ticker}.
    </p>
  );
}

function DegradedBanner({
  flags,
  factors,
}: {
  flags: string[];
  factors: FactorBreakdown[];
}) {
  const affectedNames = factors.map((f) => `${f.key.toUpperCase()} ${f.name}`).join(', ');
  return (
    <div className="atlas-fws-degraded-banner" data-testid="fws-degraded">
      <span className="atlas-fws-degraded-icon">⚠</span>
      <div className="atlas-fws-degraded-body">
        <p className="atlas-fws-degraded-title">Score degraded — partial data</p>
        <p className="atlas-fws-degraded-msg">
          One or more factors could not be computed from live data. The conviction
          score shown is unreliable and will not be cached.
        </p>
        {affectedNames && (
          <p className="atlas-fws-degraded-affected">Affected: {affectedNames}</p>
        )}
        {flags.map((flag, i) => (
          <p key={i} className="atlas-fws-degraded-flag">
            {flag}
          </p>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function FrameworkScoreContent({ data, regimeModifier }: { data: FrameworkScoreResponse; regimeModifier: number }) {
  const adjustedScore = Math.max(0, Math.min(100, data.final_score + regimeModifier));
  const setF1DisplayScore = useFrameworkStore((s) => s.setF1DisplayScore);

  // Publish the exact score the investor sees so F6, F7, and any other panel
  // consume the same value — no recomputation from a different data source.
  useEffect(() => {
    setF1DisplayScore(adjustedScore);
  }, [adjustedScore, setF1DisplayScore]);
  const toneCss = ACTION_TONE_CLASS[data.action_tone] ?? 'is-yellow';
  const filledSegs = Math.round(adjustedScore / SCORE_BAR_SEGMENTS);

  return (
    <div className="atlas-fws-content" data-testid="fws-content">
      {/* ── Hero ── */}
      <div className="atlas-fws-hero">
        <div className="atlas-fws-score-ring">
          <span className={cn('atlas-fws-score-number', toneCss)} data-testid="fws-score">
            {adjustedScore}
          </span>
          <span className="atlas-fws-score-denom">/100</span>
        </div>

        <div className="atlas-fws-hero-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-fws-action-pill', toneCss)}
            data-testid="fws-action"
          >
            {data.action}
          </span>

          <div className="atlas-fws-score-summary">
            <span className="atlas-fws-score-summary-label">Pre-regime score</span>
            <span className="atlas-fws-score-summary-value" data-testid="fws-base-score-summary">
              {data.final_score}/100
            </span>
          </div>

          {data.f5_blocked && (
            <span
              className="atlas-frameworks-pill is-red atlas-fws-block-pill"
              data-testid="fws-f5-block"
            >
              F5 HARD BLOCK
            </span>
          )}
        </div>
      </div>

      {/* ── Score bar ── */}
      <div className="atlas-fws-score-bar" aria-label={`Score: ${adjustedScore} out of 100`}>
        {Array.from({ length: SCORE_BAR_SEGMENTS }).map((_, i) => (
          <span
            key={i}
            className={cn('atlas-fws-score-seg', i < filledSegs ? toneCss : 'is-empty')}
          />
        ))}
      </div>

      {/* ── Factor breakdown table ── */}
      <div className="atlas-fws-breakdown">
        <div className="atlas-fws-breakdown-header">
          <span>Factor</span>
          <span>Score</span>
          <span>Weight</span>
          <span>Contribution</span>
        </div>
        {data.factors.map((f) => (
          <FactorRow key={f.key} factor={f} />
        ))}

        {/* ── Calculation footer ── */}
        <div className="atlas-fws-breakdown-divider" />
        <div className="atlas-fws-calc-row">
          <span className="atlas-fws-calc-label">Raw total</span>
          <span className="atlas-fws-calc-value">{data.raw_total.toFixed(2)}</span>
        </div>
        <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
          <span className="atlas-fws-calc-label">Framework score before regime</span>
          <span className={cn('atlas-fws-calc-value', toneCss)} data-testid="fws-final-score-calc">
            {data.final_score}
          </span>
        </div>
        <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
          <span className="atlas-fws-calc-label">Displayed after regime modifier</span>
          <span
            className={cn('atlas-fws-calc-value', toneCss)}
            data-testid="fws-regime-adjusted-score"
          >
            {adjustedScore}
          </span>
        </div>
      </div>

      {/* ── Flags ── */}
      {data.flags.length > 0 && (
        <div className="atlas-fws-flags" data-testid="fws-flags">
          {data.flags.map((flag, i) => (
            <p key={i} className="atlas-fws-flag-item">
              ⚠ {flag}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function buildDisplayFrameworkScore(
  data: FrameworkScoreResponse,
  scoreOverrides: Partial<Record<FactorBreakdown['key'], number | null | undefined>>,
): FrameworkScoreResponse {
  const factors = data.factors.map((factor) => buildDisplayFactor(factor, scoreOverrides[factor.key]));
  const rawTotal = calculateRawTotal(factors);
  const finalScore = calculateFinalScore(rawTotal);
  const [action, actionTone] = mapAction(finalScore);

  return {
    ...data,
    factors,
    raw_total: rawTotal,
    final_score: finalScore,
    action,
    action_tone: actionTone,
  };
}

function buildDisplayFactor(
  factor: FactorBreakdown,
  overrideScore: number | null | undefined,
): FactorBreakdown {
  if (overrideScore === undefined || overrideScore === null || !factor.available) {
    return factor;
  }

  return {
    ...factor,
    score: overrideScore,
    contribution: overrideScore * factor.weight,
  };
}

function calculateRawTotal(factors: FactorBreakdown[]): number {
  return factors.reduce((sum, factor) => sum + factor.contribution, 0);
}

function calculateFinalScore(rawTotal: number): number {
  return Math.max(0, Math.min(100, Math.round(rawTotal)));
}

function mapAction(finalScore: number): [string, string] {
  if (finalScore >= ACTION_TIER1_MIN) {
    return ['CORE / LEAPS ELIGIBLE', 'tone-green'];
  }
  if (finalScore >= ACTION_GREY_ZONE_MIN) {
    return ['GREY ZONE', 'tone-purple'];
  }
  if (finalScore >= ACTION_TIER2_MIN) {
    return ['GTC ADDS PERMITTED', 'tone-blue'];
  }
  if (finalScore >= ACTION_TIER3_MIN) {
    return ['SMALL POSITION ONLY', 'tone-yellow'];
  }
  return ['WATCHLIST', 'tone-red'];
}

// ---------------------------------------------------------------------------
// Factor row
// ---------------------------------------------------------------------------

function FactorRow({ factor }: { factor: FactorBreakdown }) {
  const gradeTone =
    factor.grade === 'STRONG BUY'
      ? 'is-green'
      : factor.grade === 'BUY'
        ? 'is-cyan'
        : factor.grade === 'NEUTRAL'
          ? 'is-yellow'
          : factor.grade === 'WEAK'
            ? 'is-orange'
            : 'is-red';

  return (
    <div
      className={cn('atlas-fws-factor-row', !factor.available && 'is-muted')}
      data-testid={`fws-factor-${factor.key}`}
    >
      <span className="atlas-fws-factor-name">
        <span className="atlas-fws-factor-key">{factor.key.toUpperCase()}</span> {factor.name}
        {!factor.available && <span className="atlas-fws-unavailable-tag"> (unavail.)</span>}
      </span>
      <span className={cn('atlas-fws-factor-score', gradeTone)}>{factor.score}</span>
      <span className="atlas-fws-factor-weight">{(factor.weight * 100).toFixed(0)}%</span>
      <span className="atlas-fws-factor-contribution">{factor.contribution.toFixed(2)}</span>
    </div>
  );
}
