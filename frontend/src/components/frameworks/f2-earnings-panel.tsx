'use client';

import { cn } from '@/lib/utils';
import { useEarnings } from '@/lib/hooks/use-earnings';
import type {
  BacklogBtbIndicator,
  EarningsResponse,
  EpsBeatsIndicator,
  GuidanceIndicator,
  MarginTrajectoryIndicator,
  RevenueGrowthIndicator,
} from '@/lib/schemas/earnings';

// ---------------------------------------------------------------------------
// Named constants — UI labels and score thresholds
// ---------------------------------------------------------------------------

/** Number of score bar segments representing the full 0-100 scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Map F2 grade string to CSS tone class name used across the design system. */
const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

/** Human-readable labels for the guidance_label categorical string. */
const GUIDANCE_LABEL: Record<string, string> = {
  RAISE_FULL_YEAR: 'Raised Full Year',
  MAINTAIN: 'Maintained',
  NARROW_RANGE: 'Narrowed Range',
  LOWER: 'Lowered',
};

/** CSS tone classes for the guidance_label categorical string. */
const GUIDANCE_TONE: Record<string, string> = {
  RAISE_FULL_YEAR: 'is-green',
  MAINTAIN: 'is-cyan',
  NARROW_RANGE: 'is-yellow',
  LOWER: 'is-red',
};

/** Human-readable labels for the backlog_label categorical string. */
const BACKLOG_LABEL: Record<string, string> = {
  EXPLICIT_MULTI_QUARTER: 'Explicit Multi-Quarter',
  STRONG: 'Strong Demand',
  LIMITED: 'Limited Visibility',
  NO_COMMENTARY: 'No Commentary',
};

/** CSS tone classes for the backlog_label categorical string. */
const BACKLOG_TONE: Record<string, string> = {
  EXPLICIT_MULTI_QUARTER: 'is-green',
  STRONG: 'is-cyan',
  LIMITED: 'is-yellow',
  NO_COMMENTARY: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F2EarningsPanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
};

/**
 * F2 Earnings Quality panel — receives the active ticker from the shared
 * selector, calls the earnings API, and shows revenue growth (YoY), EPS beat
 * history (rolling 3Q), guidance direction, gross-margin trend, and
 * backlog/visibility, plus the weighted F2 composite score.
 */
export function F2EarningsPanel({ ticker }: F2EarningsPanelProps) {
  const { data, isFetching, isError, error } = useEarnings(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f2-panel" data-testid="f2-earnings-panel">
      <header className="atlas-frameworks-panel-header atlas-f2-panel-header">
        <h2 className="atlas-frameworks-panel-title">F2 Earnings Quality</h2>
      </header>

      <div className="atlas-f2-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load earnings data.'}
          />
        )}
        {!isFetching && !isError && data && <EarningsContent data={data} />}
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
    <p className="atlas-f2-state-msg" data-testid="f2-loading">
      Analysing earnings quality…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f2-state-msg atlas-f2-state-msg--error" data-testid="f2-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f2-state-msg" data-testid="f2-empty">
      No earnings data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content — rendered when data is available
// ---------------------------------------------------------------------------

function EarningsContent({ data }: { data: EarningsResponse }) {
  const gradeTone = GRADE_TONE[data.f2_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f2-content" data-testid="f2-content">
      {/* F2 Score hero */}
      <div className="atlas-f2-score-hero">
        <div className="atlas-f2-score-ring">
          <span className={cn('atlas-f2-score-number', gradeTone)} data-testid="f2-score">
            {data.f2_score}
          </span>
          <span className="atlas-f2-score-denom">/100</span>
        </div>
        <div className="atlas-f2-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f2-grade-pill', gradeTone)}
            data-testid="f2-grade"
          >
            {data.f2_grade}
          </span>
          <span className="atlas-f2-label-sub">Earnings Quality</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f2_score} gradeTone={gradeTone} />

      {/* Indicator grid */}
      <div className="atlas-f2-indicators">
        <RevenueGrowthCard rev={data.revenue_growth} />
        <EpsBeatsCard eps={data.eps_beats} />
        <GuidanceCard guidance={data.guidance} />
        <MarginTrajectoryCard margin={data.margin_trajectory} />
        <BacklogVisibilityCard btb={data.backlog_btb} />
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
      className="atlas-f2-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f2-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator cards
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
      className="atlas-f2-indicator"
      data-testid={`f2-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f2-indicator-header">
        <span className="atlas-f2-indicator-label">{label}</span>
        <span className="atlas-f2-indicator-score">
          {score}
          <span className="atlas-f2-indicator-max">/{maxScore}</span>
        </span>
      </header>
      <div className="atlas-f2-indicator-body">{children}</div>
    </article>
  );
}

function RevenueGrowthCard({ rev }: { rev: RevenueGrowthIndicator }) {
  return (
    <IndicatorCard label="Revenue Growth" score={rev.score} maxScore={rev.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>YoY Growth</dt>
          <dd className={growthTone(rev.yoy_pct)}>
            {rev.yoy_pct !== null ? formatPct(rev.yoy_pct) : '—'}
          </dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function EpsBeatsCard({ eps }: { eps: EpsBeatsIndicator }) {
  const beatsLabel =
    eps.beats_in_3 !== null && eps.quarters_checked !== null
      ? `${eps.beats_in_3}/${eps.quarters_checked}`
      : '—';

  return (
    <IndicatorCard label="EPS Beats" score={eps.score} maxScore={eps.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Beats (Last 3Q)</dt>
          <dd className={beatsTone(eps.beats_in_3)}>{beatsLabel}</dd>
        </div>
      </dl>
      {eps.beats_in_3 !== null && eps.quarters_checked !== null && eps.quarters_checked > 0 && (
        <div className="atlas-f2-beat-bar">
          <span
            className={cn('atlas-f2-beat-bar-fill', beatsTone(eps.beats_in_3))}
            style={{ width: `${(eps.beats_in_3 / eps.quarters_checked) * 100}%` }}
          />
        </div>
      )}
    </IndicatorCard>
  );
}

function GuidanceCard({ guidance }: { guidance: GuidanceIndicator }) {
  const label = GUIDANCE_LABEL[guidance.guidance_label] ?? guidance.guidance_label;
  const tone = GUIDANCE_TONE[guidance.guidance_label] ?? 'is-yellow';

  return (
    <IndicatorCard label="Guidance" score={guidance.score} maxScore={guidance.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Direction</dt>
          <dd className={tone}>{label}</dd>
        </div>
        {guidance.transcript_quarter !== null && (
          <div className="atlas-f2-dl-row">
            <dt>Source Quarter</dt>
            <dd>{guidance.transcript_quarter}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function MarginTrajectoryCard({ margin }: { margin: MarginTrajectoryIndicator }) {
  return (
    <IndicatorCard label="Margin Trajectory" score={margin.score} maxScore={margin.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Margin Change</dt>
          <dd className={marginTone(margin.margin_change_pts)}>
            {margin.margin_change_pts !== null
              ? `${margin.margin_change_pts >= 0 ? '+' : ''}${margin.margin_change_pts.toFixed(2)} ppts`
              : '—'}
          </dd>
        </div>
      </dl>
      {margin.gross_margins.length > 0 && (
        <div className="atlas-f2-margin-sparkline">
          {margin.gross_margins.map((m, i) => (
            <div key={i} className="atlas-f2-margin-bar-wrap">
              <div
                className={cn('atlas-f2-margin-bar', marginBarTone(m))}
                style={{ height: `${Math.min(100, Math.max(5, m))}%` }}
                title={`Q${i + 1}: ${m.toFixed(1)}%`}
              />
              <span className="atlas-f2-margin-bar-label">{m.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </IndicatorCard>
  );
}

function BacklogVisibilityCard({ btb }: { btb: BacklogBtbIndicator }) {
  const label = BACKLOG_LABEL[btb.backlog_label] ?? btb.backlog_label;
  const tone = BACKLOG_TONE[btb.backlog_label] ?? 'is-yellow';

  return (
    <IndicatorCard label="Backlog Visibility" score={btb.score} maxScore={btb.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Visibility</dt>
          <dd className={tone}>{label}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Small formatting helpers — pure, no side effects
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function growthTone(value: number | null): string {
  if (value === null) return '';
  if (value >= 50) return 'is-green';
  if (value >= 10) return 'is-cyan';
  if (value >= 0) return 'is-yellow';
  return 'is-red';
}

function beatsTone(beats: number | null): string {
  if (beats === null) return '';
  if (beats >= 3) return 'is-green';
  if (beats >= 2) return 'is-cyan';
  if (beats >= 1) return 'is-yellow';
  return 'is-red';
}

function marginTone(changePts: number | null): string {
  if (changePts === null) return '';
  if (changePts > 3) return 'is-green';
  if (changePts >= 1) return 'is-cyan';
  if (changePts >= -1) return 'is-yellow';
  return 'is-red';
}

function marginBarTone(margin: number): string {
  if (margin >= 40) return 'is-green';
  if (margin >= 25) return 'is-cyan';
  if (margin >= 10) return 'is-yellow';
  return 'is-red';
}
