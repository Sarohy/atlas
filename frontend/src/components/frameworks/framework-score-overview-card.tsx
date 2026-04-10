'use client';

import { cn } from '@/lib/utils';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import type { FactorBreakdown, FrameworkScoreResponse } from '@/lib/schemas/framework-score';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTION_TONE_CLASS: Record<string, string> = {
  'tone-green': 'is-green',
  'tone-cyan': 'is-cyan',
  'tone-yellow': 'is-yellow',
  'tone-orange': 'is-orange',
  'tone-red': 'is-red',
  'tone-dark-red': 'is-red',
};

const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Compact overview card showing the live Framework Score for the currently
 * selected ticker. Sits alongside the VIX Regime, Oil Map, Geopolitical and
 * Capitulation cards in the `.atlas-frameworks-overview` grid.
 *
 * Reads the active ticker from the shared Zustand store so it always reflects
 * whatever the user has selected in the FrameworksPanelsSection below.
 */
export function FrameworkScoreOverviewCard() {
  const activeTicker = useFrameworkStore((s) => s.activeTicker);
  const { data, isLoading, isError } = useFrameworkScore(activeTicker);

  const toneCss = data ? (ACTION_TONE_CLASS[data.action_tone] ?? 'is-yellow') : 'is-cyan';

  return (
    <article
      className={cn('atlas-frameworks-overview-card atlas-fws-ov-card', toneCss)}
      data-testid="fws-overview-card"
    >
      <div className="atlas-fws-ov-header">
        <p className="atlas-fws-ov-f1-badge">F1</p>
        <p className="atlas-frameworks-overview-label">Momentum</p>
      </div>

      {isLoading && <p className="atlas-fws-ov-placeholder">Computing…</p>}
      {isError && (
        <p className="atlas-fws-ov-placeholder atlas-fws-ov-placeholder--error">Unavailable</p>
      )}
      {!isLoading && !isError && !data && (
        <p className="atlas-fws-ov-placeholder">Select a ticker</p>
      )}
      {!isLoading && !isError && data && <OverviewCardContent data={data} />}
    </article>
  );
}

// ---------------------------------------------------------------------------
// Content — rendered once data is available
// ---------------------------------------------------------------------------

function OverviewCardContent({ data }: { data: FrameworkScoreResponse }) {
  const toneCss = ACTION_TONE_CLASS[data.action_tone] ?? 'is-yellow';
  const f1 = data.factors.find((f) => f.key === 'f1');
  const f1Tone = f1 ? (GRADE_TONE[f1.grade] ?? 'is-red') : 'is-yellow';
  const otherFactors = data.factors.filter((f) => f.key !== 'f1');

  return (
    <>
      {/* F1 hero — large and prominent */}
      <div className="atlas-fws-ov-f1-hero">
        <span className={cn('atlas-fws-ov-f1-score', f1Tone)}>
          {f1?.score ?? '—'}
        </span>
        <span className="atlas-fws-ov-score-denom"> / 100</span>
        {f1 && (
          <span className={cn('atlas-frameworks-pill atlas-fws-ov-action-pill', f1Tone)}>
            {f1.grade}
          </span>
        )}
      </div>

      {/* Overall conviction + other factors */}
      <div className="atlas-fws-ov-pills">
        <span className={cn('atlas-frameworks-pill atlas-fws-ov-action-pill', toneCss)}>
          {data.action}
        </span>
        {data.f5_blocked && (
          <span className="atlas-frameworks-pill is-red atlas-fws-ov-block-pill">F5 BLOCK</span>
        )}
      </div>

      <div className="atlas-fws-ov-factors">
        {otherFactors.map((f) => (
          <FactorBadge key={f.key} factor={f} />
        ))}
      </div>

      <p className="atlas-frameworks-overview-detail">
        {data.ticker} · score {data.final_score}
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
// Factor badge
// ---------------------------------------------------------------------------

function FactorBadge({ factor }: { factor: FactorBreakdown }) {
  const gradeTone = GRADE_TONE[factor.grade] ?? 'is-red';

  return (
    <span className={cn('atlas-fws-ov-factor', gradeTone)}>
      <span className="atlas-fws-ov-factor-key">{factor.key.toUpperCase()}</span>
      <span className="atlas-fws-ov-factor-score">{factor.score}</span>
    </span>
  );
}
