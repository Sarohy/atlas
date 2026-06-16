'use client';

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { useAnalyst } from '@/lib/hooks/use-analyst';
import { useEarnings } from '@/lib/hooks/use-earnings';
import { useFundamental } from '@/lib/hooks/use-fundamental';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useMomentum } from '@/lib/hooks/use-momentum';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import { useFramework8 } from '@/lib/hooks/use-framework8';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import type { FactorBreakdown, FrameworkScoreResponse } from '@/lib/schemas/framework-score';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of score-bar segments for the full 100-pt scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Inclusive lower bounds for Framework 3 / Score Action Map bands (v7.3.5). */
const ACTION_T1_ELITE_MIN = 85;    // >= 85  → T1 ELITE / LEAPS ELIGIBLE
const ACTION_T1_MIN = 80;          // 80-84  → T1 CORE
const ACTION_TIER2_MIN = 70;       // 70-79  → GTC ADDS PERMITTED
const ACTION_TIER3_MIN = 50;       // 50-69  → SMALL POSITION ONLY
                                   // < 50   → BELOW GATE

/** CSS tone class for each action_tone string from the backend. */
const ACTION_TONE_CLASS: Record<string, string> = {
  'tone-green': 'is-green',
  'tone-teal': 'is-teal',
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
export function FrameworkScorePanel({
  ticker,
  onPreviewDetails,
}: FrameworkScorePanelProps) {
  const { data: rawData, isLoading, isError, error } = useFrameworkScore(ticker);
  const { data: rawMomentum } = useMomentum(ticker);
  const { data: rawEarnings } = useEarnings(ticker);
  const { data: rawAnalyst } = useAnalyst(ticker);
  const { data: rawOptionsFlow } = useOptionsFlow(ticker);
  const { data: rawFundamental } = useFundamental(ticker);
  const { data: rawFramework8 } = useFramework8(ticker);

  // Guard against stale data from a previous ticker. TanStack Query keeps the
  // last result mounted while the new ticker is fetching, so we must verify
  // every payload carries the current ticker symbol before rendering it.
  // Without this guard, factor scores from the previous ticker (e.g. SNDK)
  // can leak into the freshly-selected ticker's panel — producing impossible
  // pre/post-regime deltas like 75 → 73 (delta −2, while spec maximum is −10).
  const tickerMatch = ticker.trim().toUpperCase();
  const matchesActive = <T extends { ticker: string } | undefined | null>(
    payload: T,
  ): T | undefined =>
    payload && payload.ticker.toUpperCase() === tickerMatch ? payload : undefined;

  const data = matchesActive(rawData);
  const momentumData = matchesActive(rawMomentum);
  const earningsData = matchesActive(rawEarnings);
  const analystData = matchesActive(rawAnalyst);
  const optionsFlowData = matchesActive(rawOptionsFlow);
  const fundamentalData = matchesActive(rawFundamental);
  const framework8Data = matchesActive(rawFramework8);

  // ── Auto-refetch framework-score when F1-F5 OR F8 inputs change ─────────
  // Per-factor hooks (F1 momentum, F2 earnings, F3 analyst, F4 options-flow /
  // F9 override, F5 fundamental, F8 insider) own their own polling cadence.
  // When any of them returns a different value than the last render, we
  // invalidate the aggregate `framework-score` query so the backend
  // recomputes raw_total / final_score with the fresh inputs.
  // F8 is included so the panel re-renders when the buying bonus changes
  // (e.g. a new Form 4 purchase just landed) even if no F1-F5 score moved.
  const queryClient = useQueryClient();
  const prevFactorScoresRef = useRef<{
    f1: number | undefined;
    f2: number | undefined;
    f3: number | undefined;
    f4: number | undefined;
    f5: number | undefined;
    f8BuyingBonus: number | undefined;
  }>({
    f1: undefined,
    f2: undefined,
    f3: undefined,
    f4: undefined,
    f5: undefined,
    f8BuyingBonus: undefined,
  });

  const f1Score = momentumData?.f1_score ?? undefined;
  const f2Score = earningsData?.f2_score ?? undefined;
  const f3Score = analystData?.f3_score ?? undefined;
  // Match the F4 detail-card source exactly (useOptionsFlow). The F9 override
  // is shown in its own card; mixing it into the summary table caused a
  // mismatch between the F1 summary row and the F4 detail panel.
  const f4Score = optionsFlowData?.f4_score ?? undefined;
  const f5Score = fundamentalData?.f5_score ?? undefined;
  const f8BuyingBonus = framework8Data?.buying_bonus ?? undefined;

  useEffect(() => {
    const prev = prevFactorScoresRef.current;
    const next = {
      f1: f1Score,
      f2: f2Score,
      f3: f3Score,
      f4: f4Score,
      f5: f5Score,
      f8BuyingBonus,
    };
    const numericChanged = (['f1', 'f2', 'f3', 'f4', 'f5'] as const).some(
      (k) => prev[k] !== undefined && next[k] !== undefined && prev[k] !== next[k],
    );
    const f8Changed =
      prev.f8BuyingBonus !== undefined &&
      next.f8BuyingBonus !== undefined &&
      prev.f8BuyingBonus !== next.f8BuyingBonus;
    prevFactorScoresRef.current = next;
    if (numericChanged || f8Changed) {
      void queryClient.invalidateQueries({ queryKey: ['framework-score', ticker] });
    }
  }, [
    f1Score,
    f2Score,
    f3Score,
    f4Score,
    f5Score,
    f8BuyingBonus,
    ticker,
    queryClient,
  ]);

  // F5 display uses the raw score — no cap applied.
  const f5DisplayOverride = f5Score;

  const displayData = data
    ? buildDisplayFrameworkScore(
        data,
        // Use individual-hook scores as overrides so the summary table rows
        // always match the detail-card values — both now read from the same
        // per-factor API calls rather than the aggregate endpoint's independent
        // computation. F5 has the F8 cap applied above before being passed in.
        {
          f1: f1Score,
          f2: f2Score,
          f3: f3Score,
          f4: f4Score,
          f5: f5DisplayOverride,
        },
      )
    : undefined;

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel"
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
          <FrameworkScoreContent
            data={displayData}
            f4GapBadge={data?.f4_data_gap_badge ?? null}
            f4GapMessage={data?.f4_data_gap_message ?? null}
          />
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

function FrameworkScoreContent({
  data,
  f4GapBadge,
  f4GapMessage,
}: {
  data: FrameworkScoreResponse;
  f4GapBadge: string | null;
  f4GapMessage: string | null;
}) {
  // The Framework 1 conviction score is the pure framework score (F1-F5 +
  // F8 bonus). The Framework 2 regime modifier is NOT applied here — it is
  // surfaced on its own Regime Modifier / guidance panels, so F1 stands alone
  // and the score is never double-counted across panels. The headline is
  // computed locally from the per-factor hook values so the factor rows, raw
  // total, and headline always reconcile.
  const displayScore = data.final_score;
  const setF1DisplayScore = useFrameworkStore((s) => s.setF1DisplayScore);

  // Publish the exact score the investor sees so F6, F7, and any other panel
  // consume the same value — no recomputation from a different data source.
  useEffect(() => {
    setF1DisplayScore(displayScore);
  }, [displayScore, setF1DisplayScore]);
  const toneCss = ACTION_TONE_CLASS[data.action_tone] ?? 'is-yellow';
  const filledSegs = Math.round(displayScore / SCORE_BAR_SEGMENTS);

  return (
    <div className="atlas-fws-content" data-testid="fws-content">
      {/* ── Hero ── */}
      <div className="atlas-fws-hero">
        <div className="atlas-fws-score-ring">
          <span className={cn('atlas-fws-score-number', toneCss)} data-testid="fws-score">
            {displayScore}
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
      <div className="atlas-fws-score-bar" aria-label={`Score: ${displayScore} out of 100`}>
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
          <FactorRow
            key={f.key}
            factor={f}
            f4GapBadge={f.key === 'f4' ? f4GapBadge : null}
            f5CapApplied={null}
            f5RawScore={f.key === 'f5' ? data.f5_raw_score : null}
            f5CapSource={null}
          />
        ))}

        {/* ── F8 clustered selling note ── */}
        {data.f8_clustered_selling_note != null && (
          <div className="atlas-fws-f8-note" data-testid="fws-f8-clustered-note">
            ℹ {data.f8_clustered_selling_note}
          </div>
        )}

        {/* ── Calculation footer ── */}
        <div className="atlas-fws-breakdown-divider" />
        {f4GapBadge && (
          <div className="atlas-fws-f4-gap-note" data-testid="fws-f4-gap-note">
            <span className="atlas-fws-f4-gap-badge">⚠ {f4GapBadge}</span>
            {f4GapMessage && <span className="atlas-fws-f4-gap-msg"> {f4GapMessage}</span>}
          </div>
        )}
        <div className="atlas-fws-calc-row">
          <span className="atlas-fws-calc-label">Raw total</span>
          <span className="atlas-fws-calc-value">{data.raw_total.toFixed(2)}</span>
        </div>
        {/* ── F8 buying bonus note ── */}
        {data.f8_buying_bonus > 0 && (
          <div className="atlas-fws-f8-note" data-testid="fws-f8-bonus-note">
            ⬆ F8 insider buying bonus: +{data.f8_buying_bonus} pts added to raw total.
          </div>
        )}
        <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
          <span className="atlas-fws-calc-label">Framework score</span>
          <span className={cn('atlas-fws-calc-value', toneCss)} data-testid="fws-final-score-calc">
            {data.final_score}
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
  // Mirror the backend: the F8 insider-buying bonus is added to the raw total
  // before rounding/clamping (atlas/services/framework_score_service.py —
  // `_compute_final_score(raw_total + f8_buying_bonus)`). Without this the
  // "+N pts added to raw total" caption is shown but never reflected in the
  // headline, leaving the panel internally inconsistent.
  const finalScore = calculateFinalScore(rawTotal + (data.f8_buying_bonus ?? 0));
  // The Framework 2 regime modifier is intentionally NOT applied to the
  // Framework 1 conviction score (it has its own panel); the action label maps
  // directly from the pure framework score so the pill matches the headline.
  const [action, actionTone] = mapAction(finalScore);

  // When the individual-hook F5 score is used as an override, keep f5_raw_score in sync.
  const f5Override = scoreOverrides['f5'];
  const f5RawScore = f5Override !== undefined && f5Override !== null ? f5Override : data.f5_raw_score;

  return {
    ...data,
    factors,
    raw_total: rawTotal,
    final_score: finalScore,
    action,
    action_tone: actionTone,
    f5_raw_score: f5RawScore,
  };
}

function buildDisplayFactor(
  factor: FactorBreakdown,
  overrideScore: number | null | undefined,
): FactorBreakdown {
  if (overrideScore === undefined || overrideScore === null) {
    return factor;
  }

  // When a fresh per-factor hook score is available, use it even if the
  // aggregate framework-score endpoint returned `available: false` for this
  // factor (e.g. AV momentarily empty during the aggregate call). The hook
  // has its own data, so the row is no longer unavailable.
  return {
    ...factor,
    score: overrideScore,
    contribution: overrideScore * factor.weight,
    available: true,
  };
}

function calculateRawTotal(factors: FactorBreakdown[]): number {
  return factors.reduce((sum, factor) => sum + factor.contribution, 0);
}

function calculateFinalScore(rawTotal: number): number {
  return Math.max(0, Math.min(100, Math.round(rawTotal)));
}

function mapAction(finalScore: number): [string, string] {
  if (finalScore >= ACTION_T1_ELITE_MIN) {
    return ['T1 ELITE — LEAPS ELIGIBLE', 'tone-green'];
  }
  if (finalScore >= ACTION_T1_MIN) {
    return ['T1 CORE', 'tone-teal'];
  }
  if (finalScore >= ACTION_TIER2_MIN) {
    return ['GTC ADDS PERMITTED', 'tone-blue'];
  }
  if (finalScore >= ACTION_TIER3_MIN) {
    return ['SMALL POSITION ONLY', 'tone-yellow'];
  }
  return ['BELOW GATE', 'tone-red'];
}

// ---------------------------------------------------------------------------
// Factor row
// ---------------------------------------------------------------------------

function FactorRow({
  factor,
  f4GapBadge,
  f5CapApplied,
  f5RawScore,
  f5CapSource,
}: {
  factor: FactorBreakdown;
  f4GapBadge: string | null;
  f5CapApplied?: number | null;
  f5RawScore?: number | null;
  f5CapSource?: string | null;
}) {
  const gradeTone =
    factor.grade === 'STRONG BUY' || factor.grade === 'STRONG'
      ? 'is-green'
      : factor.grade === 'BUY' || factor.grade === 'GOOD'
        ? 'is-cyan'
        : factor.grade === 'NEUTRAL'
          ? 'is-yellow'
          : factor.grade === 'WEAK'
            ? 'is-orange'
            : 'is-red'; // DISTRESSED / AVOID / unknown

  return (
    <div
      className={cn('atlas-fws-factor-row', !factor.available && 'is-muted')}
      data-testid={`fws-factor-${factor.key}`}
    >
      <span className="atlas-fws-factor-name">
        <span className="atlas-fws-factor-key">{factor.key.toUpperCase()}</span> {factor.name}
        {!factor.available && <span className="atlas-fws-unavailable-tag"> (unavail.)</span>}
        {f4GapBadge && (
          <span
            className={cn(
              'atlas-fws-f4-inline-badge',
              f4GapBadge.includes('UNAVAILABLE') ? 'is-red' : 'is-amber',
            )}
            title={f4GapBadge}
          >
            {f4GapBadge}
          </span>
        )}
        {factor.key === 'f5' && f5CapApplied != null && (
          <span
            className="atlas-fws-f5-cap-badge"
            title={
              f5CapSource ??
              `F5 capped at ${f5CapApplied} by Framework 8 insider flag. Raw score: ${f5RawScore ?? '—'}.`
            }
            data-testid="fws-f5-cap-badge"
          >
            CAPPED BY F8
          </span>
        )}
      </span>
      <span className={cn('atlas-fws-factor-score', gradeTone)}>{factor.score}</span>
      <span className="atlas-fws-factor-weight">{(factor.weight * 100).toFixed(0)}%</span>
      <span className="atlas-fws-factor-contribution">{factor.contribution.toFixed(2)}</span>
    </div>
  );
}
