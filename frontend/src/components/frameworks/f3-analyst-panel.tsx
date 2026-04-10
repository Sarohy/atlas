'use client';

import { cn } from '@/lib/utils';
import { useAnalyst } from '@/lib/hooks/use-analyst';
import type {
  AnalystCoverageIndicator,
  AnalystResponse,
  ConsensusRatingIndicator,
  PtRevisionIndicator,
  PtUpsideIndicator,
} from '@/lib/schemas/analyst';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Number of score bar segments representing the full 0-100 scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Map F3 grade string to CSS tone class name. */
const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F3AnalystPanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
};

/**
 * F3 Analyst Conviction panel — receives the active ticker from the shared
 * selector and shows analyst consensus, coverage count, price-target upside,
 * and PT revision direction plus the weighted F3 composite score.
 *
 * Four sub-indicators per Factor_Mapping_Guide:
 *   Consensus Rating (35%) | Analyst Count (10%)
 *   PT vs Current Price (30%) | PT Revision Direction (25%)
 *
 * Data source: Benzinga (consensus + calendar ratings) + Polygon (price).
 */
export function F3AnalystPanel({ ticker }: F3AnalystPanelProps) {
  const { data, isFetching, isError, error } = useAnalyst(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f3-panel" data-testid="f3-analyst-panel">
      <header className="atlas-frameworks-panel-header atlas-f3-panel-header">
        <h2 className="atlas-frameworks-panel-title">F3 Analyst Conviction</h2>
      </header>

      <div className="atlas-f3-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load analyst data.'}
          />
        )}
        {!isFetching && !isError && data && <AnalystContent data={data} />}
        {!isFetching && !isError && !data && ticker && <EmptyState ticker={ticker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// State components
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <p className="atlas-f3-state-msg" data-testid="f3-loading">
      Analysing analyst conviction…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f3-state-msg atlas-f3-state-msg--error" data-testid="f3-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f3-state-msg" data-testid="f3-empty">
      No analyst data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function AnalystContent({ data }: { data: AnalystResponse }) {
  const gradeTone = GRADE_TONE[data.f3_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f3-content" data-testid="f3-content">
      {/* F3 Score hero */}
      <div className="atlas-f3-score-hero">
        <div className="atlas-f3-score-ring">
          <span className={cn('atlas-f3-score-number', gradeTone)} data-testid="f3-score">
            {data.f3_score}
          </span>
          <span className="atlas-f3-score-denom">/100</span>
        </div>
        <div className="atlas-f3-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f3-grade-pill', gradeTone)}
            data-testid="f3-grade"
          >
            {data.f3_grade}
          </span>
          <span className="atlas-f3-label-sub">Analyst Conviction</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f3_score} gradeTone={gradeTone} />

      {/* Four weighted indicator cards */}
      <div className="atlas-f3-indicators">
        <ConsensusRatingCard consensus={data.consensus_rating} />
        <AnalystCoverageCard coverage={data.analyst_coverage} />
        <PtUpsideCard pt={data.pt_upside} />
        <PtRevisionCard revision={data.pt_revision} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, gradeTone }: { score: number; gradeTone: string }) {
  const filled = Math.round((score / 100) * SCORE_BAR_SEGMENTS);

  return (
    <div
      className="atlas-f3-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f3-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator card shell
// ---------------------------------------------------------------------------

type IndicatorCardProps = {
  label: string;
  score: number;
  maxScore: number;
  children: React.ReactNode;
};

function IndicatorCard({ label, score, maxScore, children }: IndicatorCardProps) {
  return (
    <article
      className="atlas-f3-indicator"
      data-testid={`f3-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f3-indicator-header">
        <span className="atlas-f3-indicator-label">{label}</span>
        <span className="atlas-f3-indicator-score">
          {score}
          <span className="atlas-f3-indicator-max">/{maxScore}</span>
        </span>
      </header>
      <div className="atlas-f3-indicator-body">{children}</div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Individual indicator cards
// ---------------------------------------------------------------------------

function ConsensusRatingCard({ consensus }: { consensus: ConsensusRatingIndicator }) {
  return (
    <IndicatorCard
      label="Consensus Rating"
      score={Math.round(consensus.score * consensus.weight)}
      maxScore={Math.round(consensus.weight * 100)}
    >
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Consensus</dt>
          <dd className={consensusTone(consensus.label)} data-testid="f3-consensus-label">
            {consensus.label}
          </dd>
        </div>
        {consensus.buy_pct !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Buy %</dt>
            <dd>{consensus.buy_pct.toFixed(1)}%</dd>
          </div>
        )}
        <div className="atlas-f3-dl-row">
          <dt>SB / B / H / S / SS</dt>
          <dd>
            {consensus.strong_buy_count} / {consensus.buy_count} / {consensus.hold_count} /{' '}
            {consensus.sell_count} / {consensus.strong_sell_count}
          </dd>
        </div>
      </dl>
      {consensus.total_analysts > 0 && (
        <div className="atlas-f3-consensus-bar" aria-hidden="true">
          {consensus.strong_buy_count + consensus.buy_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-buy"
              style={{
                width: `${((consensus.strong_buy_count + consensus.buy_count) / consensus.total_analysts) * 100}%`,
              }}
            />
          )}
          {consensus.hold_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-hold"
              style={{ width: `${(consensus.hold_count / consensus.total_analysts) * 100}%` }}
            />
          )}
          {consensus.sell_count + consensus.strong_sell_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-sell"
              style={{
                width: `${((consensus.sell_count + consensus.strong_sell_count) / consensus.total_analysts) * 100}%`,
              }}
            />
          )}
        </div>
      )}
    </IndicatorCard>
  );
}

function AnalystCoverageCard({ coverage }: { coverage: AnalystCoverageIndicator }) {
  return (
    <IndicatorCard
      label="Analyst Count"
      score={Math.round(coverage.score * coverage.weight)}
      maxScore={Math.round(coverage.weight * 100)}
    >
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Analysts</dt>
          <dd className={coverageTone(coverage.num_analysts)}>
            {coverage.num_analysts > 0 ? coverage.num_analysts : '—'}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Reliability</dt>
          <dd>{coverageLabel(coverage.num_analysts)}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function PtUpsideCard({ pt }: { pt: PtUpsideIndicator }) {
  return (
    <IndicatorCard
      label="PT vs Current Price"
      score={Math.round(pt.score * pt.weight)}
      maxScore={Math.round(pt.weight * 100)}
    >
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Upside</dt>
          <dd className={upsideTone(pt.upside_pct)}>
            {pt.upside_pct !== null ? formatPct(pt.upside_pct) : '—'}
          </dd>
        </div>
        {pt.current_price !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Current Price</dt>
            <dd>{formatPrice(pt.current_price)}</dd>
          </div>
        )}
        {pt.consensus_pt !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Consensus PT</dt>
            <dd>{formatPrice(pt.consensus_pt)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function PtRevisionCard({ revision }: { revision: PtRevisionIndicator }) {
  return (
    <IndicatorCard
      label="PT Revision Direction"
      score={Math.round(revision.score * revision.weight)}
      maxScore={Math.round(revision.weight * 100)}
    >
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Signal</dt>
          <dd className={revisionTone(revision.revision_label)} data-testid="f3-revision-label">
            {revision.revision_label}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Raises (30d)</dt>
          <dd
            className={
              revision.raises_30d >= 2 ? 'is-green' : revision.raises_30d === 1 ? 'is-cyan' : ''
            }
          >
            {revision.raises_30d}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Lowers (30d)</dt>
          <dd className={revision.lowers_30d > 0 ? 'is-red' : ''}>{revision.lowers_30d}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting and tone helpers
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

function consensusTone(label: string): string {
  if (label === 'STRONG BUY') return 'is-green';
  if (label === 'BUY') return 'is-cyan';
  if (label === 'HOLD') return 'is-yellow';
  if (label === 'SELL') return 'is-red';
  return '';
}

function upsideTone(upside: number | null): string {
  if (upside === null) return '';
  if (upside > 30) return 'is-green';
  if (upside >= 15) return 'is-cyan';
  if (upside >= 5) return 'is-yellow';
  if (upside >= 0) return 'is-orange';
  return 'is-red';
}

function revisionTone(label: string): string {
  if (label === 'MULTIPLE RAISES') return 'is-green';
  if (label === '1 RAISE') return 'is-cyan';
  if (label === 'NO CHANGE') return 'is-yellow';
  return 'is-red'; // LOWERED
}

function coverageTone(count: number): string {
  if (count > 20) return 'is-green';
  if (count >= 10) return 'is-cyan';
  if (count >= 5) return 'is-yellow';
  return 'is-orange'; // <5 — capped at 40 pts
}

function coverageLabel(count: number): string {
  if (count > 20) return 'High';
  if (count >= 10) return 'Good';
  if (count >= 5) return 'Moderate';
  return 'Thin (<5)';
}
